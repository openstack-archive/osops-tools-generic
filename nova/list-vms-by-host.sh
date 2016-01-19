#!/bin/bash
#
# Outputs a tab-delimited list of all VMs with these fields:
# [Hypervisor Host] [UUID] [Status] [IP Address] [Name]
#
# Author: Mike Dorman <mdorman@godaddy.com>

for i in `nova list --all-tenants | grep -v '^+-' | grep -v '^| ID' |\
            awk '{print $2 "," $4 "," $6;}'`; do
    ID=`echo $i | cut -d, -f 1`
    NAME=`echo $i | cut -d, -f 2`
    STATUS=`echo $i | cut -d, -f 3`

    SHOW=`nova show ${ID}`
    HV=`echo "${SHOW}" | grep OS-EXT-SRV-ATTR:host | awk '{print $4;}'`
    IP=`echo "${SHOW}" | grep " network" | awk '{print $5;}'`

    echo -e "${HV}\t${ID}\t${STATUS}\t${IP}\t${NAME}"
done
