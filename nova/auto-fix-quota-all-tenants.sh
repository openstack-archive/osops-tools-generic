#!/bin/bash

usage() {
    echo "Usage: $0 [-n] [-q]"
    echo "-n: Dry Run. Don't update the database"
    echo "-q: Quiet mode. Only show incorrect quotas"
    exit 1
}

while getopts ":nq" opt ; do
    case ${opt} in
        n)
            base_msg="[DRY RUN] "
            args="${args} -n"
            ;;
        q)
            args="${args} -q"
            ;;
        *)
            usage
            ;;
    esac
done


echo "$(date): Tenant quota correction - started"

for x in $(keystone --insecure tenant-list | awk -F' |\
    ' '!/^\+/ && !/\ id\ / {print $2}'); do
    msg="${base_msg}Correcting quota for tenant ${x}"
    echo ${msg}
    python ./auto-fix-quota.py ${args} --tenant ${x}
done

echo "$(date): Tenant quota correction - finished"
