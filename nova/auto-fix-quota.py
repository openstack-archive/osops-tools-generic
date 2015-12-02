#!/usr/bin/python
"""
 Author: amos.steven.davis@hp.com
 Description: Fix nova quota in the nova database when the acutal usage
 and what nova thinks is the quota do not match.
"""
from nova import db
from nova import config
from nova import context
from nova import exception
from collections import OrderedDict
import argparse
import prettytable
import bpdb


def make_table(name, *args):
    q = prettytable.PrettyTable(name)
    q.align = "c"
    q.add_row(args[0])
    return q


def get_actual_usage(cntxt, tenant):
    filter_object = {'deleted': '',
                     'project_id': tenant}
    instances = db.instance_get_all_by_filters(cxt, filter_object)

    # calculate actual usage
    actual_instance_count = len(instances)
    actual_core_count = 0
    actual_ram_count = 0

    for instance in instances:
        actual_core_count += instance['vcpus']
        actual_ram_count  += instance['memory_mb']

    actual_secgroup_count = len(db.security_group_get_by_project(cxt,tenant))

    return OrderedDict((
        ("actual_instance_count", actual_instance_count),
        ("actual_core_count", actual_core_count),
        ("actual_ram_count", actual_ram_count),
        ("actual_secgroup_count", actual_secgroup_count)
    ))


def get_incorrect_usage(cntxt, tenant):
    existing_usage = db.quota_usage_get_all_by_project(cntxt, tenant)
    # {u'ram': {'reserved': 0L, 'in_use': 0L},
    #  u'floating_ips': {'reserved': 0L, 'in_use': 1L},
    #  u'instances': {'reserved': 0L, 'in_use': 0L},
    #  u'cores': {'reserved': 0L, 'in_use': 0L},
    #  'project_id': tenant,
    #  u'security_groups': {'reserved': 0L, 'in_use': 1L}}
    #
    # Get (instance_count, total_cores, total_ram) for project.
    # If instances does not exist,  then this

    try:
      security_groups = existing_usage["security_groups"]["in_use"]
    except KeyError:
      security_groups = 1

    try:
      instances = existing_usage["instances"]["in_use"]
    except KeyError:
      instances = 0

    try:
      cores = existing_usage["cores"]["in_use"]
    except KeyError:
      cores = 0

    try:
      ram = existing_usage["ram"]["in_use"]
    except KeyError:
      ram = 0

    return OrderedDict((
        ("db_instance_count", instances),
        ("db_core_count", cores),
        ("db_ram_count", ram),
        ("db_secgroup_count", security_groups)
    ))


def fix_usage(cntxt, tenant):
    print "\nUpdating quota usage to reflect actual usage..\n"

    # Get per-user data for this tenant since usage is now per-user
    filter_object = { 'project_id': tenant }
    instance_info = db.instance_get_all_by_filters(cntxt, filter_object)

    usage_by_resource = {}
    #resource_types = ['instances', 'cores', 'ram', 'security_groups']
    states_to_ignore = ['error','deleted','building']

    for instance in instance_info:
        user = instance['user_id']
        # We need to build a list of users who have launched vm's even if the user
        # no longer exists. We can't use keystone here.
        if not usage_by_resource.has_key(user):
          usage_by_resource[user] = {} # Record that this user has once used resources
        if not instance['vm_state'] in states_to_ignore:
          user_resource = usage_by_resource[user]
          user_resource['instances'] = user_resource.get('instances', 0) + 1
          user_resource['cores'] = user_resource.get('cores', 0) + instance['vcpus']
          user_resource['ram'] = user_resource.get('ram', 0) + instance['memory_mb']

    secgroup_list = db.security_group_get_by_project(cntxt,tenant)
    for group in secgroup_list:
      user = group.user_id
      if not usage_by_resource.has_key(user):
        usage_by_resource[user] = {} # Record that this user has once used resources
      user_resource = usage_by_resource[user]
      user_resource['security_groups'] = user_resource.get('security_groups', 0) + 1

    # Correct the quota usage in the database
    for user in usage_by_resource:
      for resource in resource_types:
        usage = usage_by_resource[user].get(resource, 0)
        try:
          db.quota_usage_update(cntxt, tenant, user, resource, in_use=usage)
        except exception.QuotaUsageNotFound as e:
          print e
          print 'db.quota_usage_update(cntxt, %s, %s, %s, in_use=%s)' % (tenant, user, resource, usage)
          pass

    print_usage(cntxt, tenant)

def print_usage(context, tenant):
    actual_table_name = ["Actual Instances",
			 "Actual Cores",
			 "Actual RAM",
			 "Actual Security_Groups"]

    # these are spaced so that the Quota & DB tables match in size
    incorrect_table_name = ["  DB Instances  ",
			    "  DB Cores  ",
			    "  DB RAM  ",
			    "  DB Security_Groups  "]

    print "############### Actual Usage (including non-active instances) ###############"
    print make_table(actual_table_name, get_actual_usage(cxt, tenant).values())
    print "############### Database Usage ###############"
    print make_table(incorrect_table_name, get_incorrect_usage(cxt, tenant).values())

resource_types = ['instances', 'cores', 'ram', 'security_groups']
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

print_usage(cxt, tenant)

# if the actual usage & the quota tracking differ,
# update quota to match reality
try:
  actual = get_actual_usage(cxt, tenant).values()
  incorrect = get_incorrect_usage(cxt, tenant).values()
except:
  exit()

if actual == incorrect:
    print "\n%s quota is OK" % tenant
elif args.dryrun:
    print "Dry Run Mode Enabled - not correcting the quota database."
else:
    fix_usage(cxt, tenant)

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
