#!/usr/bin/env bash
#
# Run this script on a compute node to cleanup/remove any orphaned KVM VMs that were left behind by something.
# Run with --noop to do a dry run and not actually delete anything
#
# To populate the UUIDS value below, run the following command on a Nova api server to get list of VM UUIDs that are known to OpenStack:
#  nova list --all-tenants | awk '{print $2;}' | grep -E '^[0-9a-f]+' | tr '\n' '|' | sed -r 's/\|$/\n/'
# Then paste in the results for UUIDS below OR define it in the environment before running this script.
#
# Author: Kris Lindgren <klindgren@godaddy.com>
#

#UUIDS=""

if [ -z "$UUIDS" ]; then
    echo "UUIDS value not defined"
    exit 1
fi

for uuid in `virsh list --uuid --all` ; do

    echo $uuid | grep -E "$UUIDS" >/dev/null
    if [ $? -ne 0 ]; then
        echo -n "+ $uuid is NOT known to OpenStack, removing managedsave info... "
        [ -z "$1" ] && virsh managedsave-remove $uuid 1>/dev/null 2>&1
        echo -n "destroying VM... "
        [ -z "$1" ] && virsh destroy $uuid 1>/dev/null 2>&1
        echo -n "undefining VM... "
        [ -z "$1" ] && virsh undefine $uuid 1>/dev/null 2>&1
        echo DONE
    else
        echo "* $uuid is known to OpenStack, not removing."
    fi

done
