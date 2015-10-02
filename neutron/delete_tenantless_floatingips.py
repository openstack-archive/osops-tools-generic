#!/usr/bin/env python

"""
This script deletes all the floatingips a user has that are not
associated with a tenant.
"""

import os
import sys

from neutronclient.v2_0 import client
import keystoneclient.v2_0.client as ksclient

def main():

    dry_run = (len(sys.argv) > 1 and sys.argv[1] == '--dry-run')

    try:
        username = os.environ['OS_USERNAME']
        tenant_name = os.environ['OS_TENANT_NAME']
        password = os.environ['OS_PASSWORD']
        auth_url = os.environ['OS_AUTH_URL']
    except KeyError:
        print("You need to source your openstack creds file first!")
        sys.exit(1)

    neutron = client.Client(username=username,
                            tenant_name=tenant_name,
                            password=password,
                            auth_url=auth_url)

    keystone = ksclient.Client(username=username,
                            tenant_name=tenant_name,
                            password=password,
                            auth_url=auth_url)

    floatingips = neutron.list_floatingips()
    for floatingip in floatingips['floatingips']:
        try:
            keystone.tenants.get(floatingip['tenant_id'])
        # If the tenant ID doesn't exist, then this object is orphaned
        except ksclient.exceptions.NotFound:
            print(("Deleting floatingip %s - %s") %
                  (floatingip['id'], floatingip['floating_ip_address']))
            if not dry_run:
                neutron.delete_floatingip(floatingip['id'])

main()
