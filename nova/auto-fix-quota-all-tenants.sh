#!/bin/bash

echo "$(date): Tenant quota correction - started"

for x in $(openstack project list -f csv -c ID --quote none | tail -n +2);
do
   #echo "Correcting quota for tenant $x"
   ./auto-fix-quota.py --quiet --dryrun --tenant $x 
   #echo
done

echo "$(date): Tenant quota correction - finished"

