#!/bin/bash
source /root/scripts/stackrc

echo "$(date): Tenant quota correction - started"

for x in $(keystone --insecure tenant-list | awk -F' | ' '!/^\+/ && !/\ id\ / {print $2}');
do
   echo "Correcting quota for tenant $x"
   python /root/scripts/auto-fix-quota.py --tenant $x
done

echo "$(date): Tenant quota correction - finished"

