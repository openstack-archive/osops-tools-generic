"""
This script deletes all the floatingips a user has that are not
associated with a port_id.
"""

import os
import sys

from neutronclient.v2_0 import client


def main():
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

    floatingips = neutron.list_floatingips()
    for floatingip in floatingips['floatingips']:
        if not floatingip['port_id']:
            print(("Deleting floatingip %s - %s") %
                  (floatingip['id'], floatingip['floating_ip_address']))
            neutron.delete_floatingip(floatingip['id'])

main()
