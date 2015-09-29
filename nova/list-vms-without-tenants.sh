#!/bin/bash
#
# Lists VMs which have been orphaned from their tenant (i.e. the tenant
# was removed, but VMs were still in the tenant.)
#
# Author: Kris Lindgren <klindgren@godaddy.com>

echo "THIS SCRIPT NEED TO HAVE keystonerc sourced to work"
sleep 5

echo "Getting a list of vm's from nova..."
novavmsraw=$( nova list --all-tenants --fields name,tenant_id,user_id )
echo "done."
echo "Getting a list of tenants from keystone...."
keystoneraw=$( keystone tenant-list )
echo "done."
novatenants=$( echo "$novavmsraw" | awk '{print $6}' | sort | uniq | grep -v Tenant )
echo "Starting to list vm's that are no longer attached to a tenant..."
echo "Fields are:"
echo "|  VM ID                               |     VM Name                               | Tenant Id                        | User Id        |"
for i in $novatenants; do
    tmp=$( echo "$keystoneraw" | grep $i )
    if [ $? -eq 0 ]; then
        continue
    else
        vms=$( echo "$novavmsraw" | grep $i )
        echo "$vms"
    fi
done
