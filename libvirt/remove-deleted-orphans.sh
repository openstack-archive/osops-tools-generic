#!/bin/bash
#
# This script will look at the configured vm's and will check to make sure that their disk drive still exists,
# If not then it will remove the vm from libvirt.  This fixes the nova errors about disks missing from VM's
#
# Author: Kris Lindgren <klindgren@godaddy.com>
#

removeorphan(){
    local domain
    local tmp
    domain=$1
 
    tmp=$( virsh destroy $domain )
    tmp=$( virsh undefine $domain )
    tmp=$(virsh list --all | grep $domain )
    if [ $? -eq 1 ]; then
        tmp=$( ps auxwwwf | grep $domain | grep -v grep )
        if [ $? -eq 1 ]; then
            return 0
        fi
    fi
    return 1
}
 
for i in /etc/libvirt/qemu/*.xml; do
    disklocation=$( grep /var/lib/nova/instances $i | grep disk | cut -d"'" -f2,2)
    if [ ! -e $disklocation ]; then
        orphan=$(echo $i | cut -d"/" -f5,5 | cut -d"." -f1,1)
        echo "$orphan does not have a disk located at: $disklocation"
        echo "This is an orphan of openstack... stopping the orphaned vm."
        removeorphan $orphan
        if [ $? -eq 0 ]; then
            echo "Domain $orphan has been shutdown and removed"
        else
            echo "Domain $orphan has *NOT* been shutdown and removed"
        fi
    fi
done
