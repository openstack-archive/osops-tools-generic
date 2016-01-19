#!/bin/bash
#
# A quick and dirty script to backfill empty config drive
# images to VMs that don't already have a config drive.
#
# This is a workaround for the config drive bug described
# at https://bugs.launchpad.net/nova/+bug/1356534
#
# Author: Mike Dorman <mdorman@godaddy.com>

cd /root
mkdir -p blank
mkisofs -o blank.iso blank/ >/dev/null 2>&1
rmdir blank

for i in `ls /var/lib/nova/instances | \
    grep -E '[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}'`; do
    ls -l /var/lib/nova/instances/$i/disk.config
    if [ ! -s /var/lib/nova/instances/$i/disk.config ]; then
        echo "$i config drive doesn't exist, or is size zero."
        cp -f /root/blank.iso /var/lib/nova/instances/$i/disk.config
        chown qemu:qemu /var/lib/nova/instances/$i/disk.config
    fi
done
