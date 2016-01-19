#!/bin/bash

# OpenStack credentials are expected to be in your environment variables
if [ -z "$OS_AUTH_URL" -o -z "$OS_PASSWORD" -o -z "$OS_USERNAME" ]; then
    echo "Please set OpenStack auth environment variables."
    exit 1
fi

# temp files used for caching outputs
vm_tenants=$(mktemp)
keystone_tenants=$(mktemp)

# get a list of all VMs in the cluster and who they belong to
echo -en "Retrieving list of all VMs...\r"
nova list --all-tenants --fields tenant_id | tail -n +4 | awk '{print $4}' |\
    sort -u > $vm_tenants
total_vms=$(cat $vm_tenants | wc -l)
if [ $total_vms == 0 ]; then
    echo "Zero VMs found. Exiting..."
    rm -f $vm_tenants $keystone_tenants
    exit 1
fi

# get a list of all tenants/projects in the cluster
echo -en "Retrieving list of all tenants...\r"
keystone tenant-list | tail -n +4 | awk '{print $2}' |\
    sort -u > $keystone_tenants
total_tenants=$(cat $keystone_tenants | wc -l)
if [ $total_tenants == 0 ]; then
    echo "Zero tenants found. Exiting..."
    rm -f $vm_tenants $keystone_tenants
    exit 1
fi

# compare all VM owners to all tenants as reported by keystone and print
# any VMs whose owner does not exist in keystone
echo -en "Comparing outputs to locate orphaned VMs....\r"
iter=0
for tenant_id in `comm --nocheck-order -13 $keystone_tenants $vm_tenants`; do
    if [[ $iter == 0 ]]; then
        nova list --all-tenants --tenant=$tenant_id \
            --fields tenant_id,name,status,created,updated | head -n -1
        let "iter++"
    else
        nova list --all-tenants --tenant=$tenant_id \
            --fields tenant_id,name,status,created,updated | \
            tail -n +4 | head -n -1
    fi
done

# cleanup after ourself
rm $keystone_tenants $vm_tenants
