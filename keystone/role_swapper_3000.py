#!/usr/bin/python

__author__      = 'Matt Fischer <matt.fischer@twcable.com>'
__copyright__   = 'Copyright 2015, Matt Fischer'

# This tool lets you swap roles or list roles that might need to be swapped.
# The use case is when you decide that you need to rename a role and would
# rather not modify the DB directly. This script will NOT create or remove the
# actual role, but it will find users with Role OLD and grant them Role NEW and
# optionally then remove Role OLD.
#
# Usage Examples:
#
# To see who is still holding the old role:
# ./role_swapper_3000.py --old_role <old> --new_role <new>
#
# To remove the old role from anyone who has it (dangerous)
# ./role_swapper_3000.py --remove --old_role <old> --new_role <new>
# (this is dangerous because now you lack any record of the role
# that you intended to swap)
#
# To add the new role and remove the old role
# ./role_swapper_3000.py --add --old_role <old> --new_role <new>
#
# To add the new role only. This can be used when you've got
# services and tools that may refer to either the old or
# new role.
# ./role_swapper_3000.py --add --remove --old_role <old> --new_role <new>
#
# Warning:
#
# If you modify the roles for the user running the script their token
# gets invalidated and the script will abort. It's ideimpotent so you
# should be able to just run it again.

from keystoneclient.v2_0 import client
import argparse
import os
keystone = None

def main(old_role, new_role, add, remove):
    global keystone
    keystone = client.Client(username=os.environ.get('OS_USERNAME'),
            password=os.environ.get('OS_PASSWORD'),
            tenant_name=os.environ.get('OS_TENANT_NAME'),
            region_name=os.environ.get('OS_REGION_NAME'),
            auth_url=os.environ.get('OS_AUTH_URL'))
    swap_roles_for_tenant(old_role, new_role, add, remove)

# assumes no typos on role-name
def lookup_role_id(keystone, role_name):
    role_ids = keystone.roles.findall(name=role_name)
    if len(role_ids) != 1:
        print "Found %d matches for %s in role list, fatal." % (len(role_ids), role_name)
        return '-1'
    return role_ids[0].id

def user_already_has_role(keystone, role_id, user, tenant):
    roles = keystone.roles.roles_for_user(user, tenant)
    for role in roles:
        if role.id == role_id:
            return True
    return False

def swap_roles_for_tenant(old_role, new_role, add, remove):
    tenants = keystone.tenants.list()

    new_role_id = lookup_role_id(keystone, new_role)
    old_role_id = lookup_role_id(keystone, old_role)

    print "Scanning tenants for role %s" % (old_role)
    for tenant in tenants:
        print "Tenant %s" % tenant.name
        print "---------------------------------------"
        for user in tenant.list_users():
            roles = user.list_roles(tenant=tenant.id)
            for role in roles:
                if role.name == old_role:
                    print "\tUser: %s <%s> has %s" % (user.name, user.email, role.name)
                    if add:
                        if user_already_has_role(keystone, new_role_id, user, tenant):
                            print "\t\tSkipping %s. Already has %s" % (user.name, new_role)
                        else:
                            print "\t\tAdding %s to %s who already has %s" % (new_role, user.name, old_role)
                            keystone.tenants.role_manager.add_user_role(user=user, role=new_role_id, tenant=tenant)
                    if remove:
                        print "\t\tRemoving %s" % (old_role)
                        keystone.tenants.role_manager.remove_user_role(user=user,
                            role=old_role_id, tenant=tenant)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--old_role", required=True)
    parser.add_argument("--new_role", required=True)
    parser.add_argument("--add", action='store_true', help='Set this if you really want the new role added')
    parser.add_argument("--remove", action='store_true', help='Set this if you really want the old role removed')
    args = parser.parse_args()
    main(args.old_role, args.new_role, args.add, args.remove)
