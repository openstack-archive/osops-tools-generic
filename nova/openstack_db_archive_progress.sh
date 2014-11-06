#!/bin/bash
#
# Copyright 2012 Hewlett-Packard Development Company, L.P. All Rights Reserved.
#
# Author: Simon McCartney <simon.mccartney@hp.com>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

# Report on the current state of unarchived records in the main nova.* tables
#


DATABASE=nova
TABLES="security_group_rules security_group_instance_association security_groups instance_info_caches instance_system_metadata instances reservations compute_node_stats "

for TABLE in ${TABLES}
do
    SHADOW_TABLE="shadow_${TABLE}"

    ACTIVE_RECORDS=`mysql -B -e "select count(id) from ${DATABASE}.${TABLE} where deleted=0" | tail -1`
    DELETED_RECORDS=`mysql -B -e "select count(id) from ${DATABASE}.${TABLE} where deleted!=0" | tail -1`
    SHADOW_RECORDS=`mysql -B -e "select count(id) from ${DATABASE}.${SHADOW_TABLE}" | tail -1`
    TOTAL_RECORDS=`expr $ACTIVE_RECORDS + $DELETED_RECORDS + $SHADOW_RECORDS`

    echo `date` "${DATABASE}.${TABLE} has ${ACTIVE_RECORDS}, ${DELETED_RECORDS} ready for archiving and ${SHADOW_RECORDS} already in ${SHADOW_TABLE}. Total records is ${TOTAL_RECORDS}"
done
