#!/usr/bin/env python
import os
import sys
import keystoneclient.v2_0.client as ksclient
import neutronclient.v2_0.client as nclient


def get_credentials():
    credentials = {}
    credentials['username'] = os.environ['OS_USERNAME']
    credentials['password'] = os.environ['OS_PASSWORD']
    credentials['auth_url'] = os.environ['OS_AUTH_URL']
    credentials['tenant_name'] = os.environ['OS_TENANT_NAME']
    if 'OS_REGION_NAME' in os.environ:
        credentials['region_name'] = os.environ['OS_REGION_NAME']
    return credentials


CREDENTIALS = get_credentials()
NEUTRON = nclient.Client(**CREDENTIALS)
KEYSTONE = ksclient.Client(**CREDENTIALS)


def usage():
    print("listorphans.py <object> where object is one or more of ")
    print("'networks', 'routers', 'subnets', 'floatingips' or 'all'")


def get_tenantids():
    return [tenant.id for tenant in KEYSTONE.tenants.list()]


def get_orphaned_neutron_objects(neutron_obj):
    neutron_objs = getattr(NEUTRON, 'list_' + neutron_obj)()
    tenantids = get_tenantids()
    orphans = []
    for neutron_obj in neutron_objs.get(neutron_obj):
        if neutron_obj['tenant_id'] not in tenantids:
            orphans.append(object['id'])
    return orphans


if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == 'all':
            neutron_objs = ['networks', 'routers', 'subnets', 'floatingips']
        else:
            neutron_objs = sys.argv[1:]
        for neutron_obj in neutron_objs:
            orphans = get_orphaned_neutron_objects(neutron_obj)
            print('%s orphan(s) found of type %s' % (len(orphans),
                                                     neutron_obj))
            print('\n'.join(map(str, orphans)))

    else:
        usage()
        sys.exit(1)
