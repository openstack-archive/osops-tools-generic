#!/usr/bin/env python

import os
import sys
import keystoneclient.v2_0.client as ksclient
import neutronclient.v2_0.client as nclient

def usage():
    print "listorphans.py <object> where object is one or more of",
    print "'networks', 'routers', 'subnets', 'floatingips' or 'all'"

def get_credentials():
    d = {}
    d['username'] = os.environ['OS_USERNAME']
    d['password'] = os.environ['OS_PASSWORD']
    d['auth_url'] = os.environ['OS_AUTH_URL']
    d['tenant_name'] = os.environ['OS_TENANT_NAME']
    return d

credentials = get_credentials()
neutron = nclient.Client(**credentials)
keystone = ksclient.Client(**credentials)

def get_tenantids():
    return [tenant.id for tenant in keystone.tenants.list()]

def get_orphaned_neutron_objects(object):
    objects = getattr(neutron, 'list_' + object)()
    tenantids = get_tenantids()
    orphans = []
    for object in objects.get(object):
        if object['tenant_id'] not in tenantids:
            orphans.append(object['id'])
    return orphans

if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == 'all':
            objects = [ 'networks', 'routers', 'subnets', 'floatingips' ]
        else:
            objects = sys.argv[1:]
        for object in objects:
            orphans = get_orphaned_neutron_objects(object)
            print len(orphans), 'orphan(s) found of type', object
            print '\n'.join(map(str, orphans))
    else:
        usage()
        sys.exit(1)
