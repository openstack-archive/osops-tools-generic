#!/bin/bash

#Accounts
source /root/openrc

# Usage
USAGE="Usage: ./simple-script.sh TENANT_NAME NUMBER_OF_VMs"

if [ $# -ne 2 ]; then
    echo "$USAGE"
    exit 1
fi

# Getting Member Role
MEMBER_ROLE=$(keystone role-list | grep " _member_ " | awk '{print $2}')
echo $MEMBER_ROLE

# User
TENANT=$(keystone tenant-create \
   --name=$1 \
   | grep " id " | awk '{print $4}')
echo $TENANT

USER=$(keystone user-create \
        --name $1 \
        --pass “supersecure!” \
        --email $1@example.com \
        | grep " id " | awk '{print $4}')
echo $USER
keystone user-role-add --user_id $USER --role_id $MEMBER_ROLE --tenant_id $TENANT

# Create an RC file for this user and source the credentials
cat >> keystonerc_$1<<EOF
export OS_USERNAME=$1
export OS_TENANT_NAME=$1
export OS_PASSWORD=supersecure!
export OS_AUTH_URL=http://localhost:5000/v2.0/
EOF


# Source this user credentials
source keystonerc_$1

echo "Creating Private Network"
neutron net-create mynetwork
echo "Creating Private Subnet"
neutron subnet-create mynetwork 5.5.5.0/24 --gateway 5.5.5.254 --name mysubnet

echo "Starting VM on Private "
for i in {1..$2}
do
nova boot --flavor 1 --image cirros vm_$i
done
echo "Done - VMs"

