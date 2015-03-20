#!/usr/bin/python
"""
 Author: amos.steven.davis@hp.com
 Description: Fix nova quota in the nova database when the acutal usage
 and what nova thinks is the quota do not match.
"""
from nova import db
from nova import config
from nova import context
from collections import OrderedDict
import argparse
import prettytable


def make_table(name, *args):
    q = prettytable.PrettyTable(name)
    q.align = "c"
    q.add_row(args[0])
    return q


def get_actual_usage(cntxt, tenant):
    instance_info = db.instance_data_get_for_project(cxt, tenant)

    # calculate actual usage
    actual_instance_count = instance_info[0]
    actual_core_count = instance_info[1]
    actual_ram_count = instance_info[2]

    # actual_fixed_ips should be the same as actual_instance_count since there is no
    # reason in our environment for someone to use two fixed IPs per instance
    # db.fixed_ip_count_by_project(cxt,tenant)
    actual_fixed_ips = actual_instance_count
    actual_secgroup_count = db.security_group_count_by_project(cxt, tenant)

    return OrderedDict((
        ("actual_instance_count", actual_instance_count),
        ("actual_core_count", actual_core_count),
        ("actual_ram_count", actual_ram_count),
        ("actual_fixed_ips", actual_fixed_ips),
        ("actual_secgroup_count", actual_secgroup_count)
    ))


def get_incorrect_usage(cntxt, tenant):
    existing_usage = db.quota_usage_get_all_by_project(cntxt, tenant)
    # {u'ram': {'reserved': 0L, 'in_use': 0L},
    #  u'floating_ips': {'reserved': 0L, 'in_use': 1L},
    #  u'instances': {'reserved': 0L, 'in_use': 0L},
    #  u'cores': {'reserved': 0L, 'in_use': 0L},
    #  'project_id': tenant,
    #  u'fixed_ips': {'reserved': 0L, 'in_use': 0L},
    #  u'security_groups': {'reserved': 0L, 'in_use': 1L}}
    #
    # Get (instance_count, total_cores, total_ram) for project.
    # If instances does not exist,  then this
    if 'instances' in existing_usage:
        # it's possible for accounts to use nothing but the system default
        # group, which doesn't get tracked, so default to 1
        try:
            security_groups = existing_usage["security_groups"]["in_use"]
        except KeyError:
            security_groups = 1

        return OrderedDict((
            ("db_instance_count", existing_usage["instances"]["in_use"]),
            ("db_core_count", existing_usage["cores"]["in_use"]),
            ("db_ram_count", existing_usage["ram"]["in_use"]),
            ("db_fixed_ips", existing_usage["fixed_ips"]["in_use"]),
            ("db_secgroup_count", security_groups)
        ))
    else:
        print "%s get_incorrect_usage failed to find quota usage information in " \
              "database.  Is this tenant in use?" % tenant
        exit(0)


def fix_usage(cntxt, tenant, actual_table_name, incorrect_table_name):
    print "\nUpdating quota usage to reflect actual usage..\n"
    # Calculate differences
    existing_usage = db.quota_usage_get_all_by_project(cntxt, tenant)
    actual = get_actual_usage(cntxt, tenant)

    # it's possible for accounts to use nothing but the system default
    # group, which doesn't get tracked, so default to 0
    try:
        security_groups = existing_usage["security_groups"]["in_use"]
        secgroup_difference = security_groups - actual["actual_secgroup_count"]
    except KeyError:
        security_groups = None

    instance_difference = \
        existing_usage["instances"]["in_use"] - actual["actual_instance_count"]
    core_difference = \
        existing_usage["cores"]["in_use"] - actual["actual_core_count"]
    ram_difference = \
        existing_usage["ram"]["in_use"] - actual["actual_ram_count"]
    # Actual_fixed_ips should be the same as actual_instance_count since there is no
    # Reason in our environment for someone to use two fixed IPs
    # existing_usage["fixed_ips"]["in_use"]-actual["actual_fixed_ips"]
    fixedips_difference = \
        existing_usage["fixed_ips"]["in_use"] - actual["actual_instance_count"]
    # Quota_usage_update(context, project_id, resource, **kwargs)
    # Update ram.
    db.quota_usage_update(cxt,
                          tenant,
                          'ram',
                          in_use=existing_usage["ram"]["in_use"] -
                          ram_difference)
    # Update instances
    db.quota_usage_update(cxt,
                          tenant,
                          'instances',
                          in_use=existing_usage["instances"]["in_use"] -
                          instance_difference)
    # Update cores
    db.quota_usage_update(cxt,
                          tenant,
                          'cores',
                          in_use=existing_usage["cores"]["in_use"] - core_difference)
    # Update fixed IPs
    """
    db.quota_usage_update(cxt,
                          tenant,
                          'fixed_ips',
                          in_use=existing_usage["fixed_ips"]["in_use"] - fixedips_difference)
    """

    # Update security groups
    if security_groups is not None:
        db.quota_usage_update(cxt,
                              tenant,
                              'security_groups',
                              in_use=security_groups - secgroup_difference)

    print "############### Actual Usage (including non-active instances) ###############"
    print make_table(actual_table_name, get_actual_usage(cxt, tenant).values())
    print "############### Corrected Database Usage ###############"
    print make_table(incorrect_table_name, get_incorrect_usage(cxt, tenant).values())


actual_table_name = ["Actual Instances",
                     "Actual Cores",
                     "Actual RAM",
                     "Actual Fixed_ips",
                     "Actual Security_Groups"]

# these are spaced so that the Quota & DB tables match in size
incorrect_table_name = ["  DB Instances  ",
                        "  DB Cores  ",
                        "  DB RAM  ",
                        "  DB Fixed_ips  ",
                        "  DB Security_Groups  "]

config.parse_args(['filename', '--config-file', '/etc/nova/nova.conf'])

# Get other arguments
parser = argparse.ArgumentParser(
    description='Fix quota differences between reality and the database')
parser.add_argument('--tenant', help='Specify tenant', required=True)
parser.add_argument('-n', '--dryrun', help='Dry Run - don\'t update the database',
                    action="store_true")
args = parser.parse_args()
tenant = args.tenant

# Get admin context
cxt = context.get_admin_context()

print "############### Actual Usage (including non-active instances) ###############"
print make_table(actual_table_name, get_actual_usage(cxt, tenant).values())
print "############### Database Usage ###############"
print make_table(incorrect_table_name, get_incorrect_usage(cxt, tenant).values())

# if the actual usage & the quota tracking differ,
# update quota to match reality
if get_incorrect_usage(cxt, tenant).values() == get_actual_usage(cxt, tenant).values():
    print "\n%s quota is OK" % tenant
elif args.dryrun:
    print "Dry Run Mode Enabled - not correcting the quota database."
else:
    fix_usage(cxt, tenant, actual_table_name, incorrect_table_name)

# This section can replace the final if/else statement to allow prompting for
#   each tenant before changes happen
# if get_incorrect_usage(cxt,tenant).values() == get_actual_usage(cxt,tenant).values():
#    print "%s quota is OK" % tenant
# else:
#    if raw_input("Enter 'YES' to make the Database Usage match the Actual Usage.  " \
#       "This will modify the Nova database: ") != "YES":
#        print "Exiting."
#        exit(0)
#    else:
#        fix_usage(cxt,tenant,actual_table_name,incorrect_table_name)
