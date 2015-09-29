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
#
# purge tables of "deleted" records by archiveing them in sensible chunks to the shadow tables
# this work was started in PAASINFRA-206
#

# default to archiving all records flagged as deleted,
# use the -n option to enable dry run mode
unset DRY_RUN

# tables to arhive deleted records from
DATABASE=nova
TABLES="security_group_rules security_group_instance_association security_groups instance_info_caches instances reservations compute_node_stats"
FKTABLES="block_device_mapping instance_metadata instance_system_metadata instance_actions instance_faults virtual_interfaces fixed_ips security_group_instance_association migrations instance_extra"
TABLES="${TABLES} ${FKTABLES}"

## process the command line arguments
while getopts "hnad:H:u:p:" opt; do
  case $opt in
    h)
      echo "openstack_db_archive.sh - archive records flagged as deleted into the shadow tables."
      echo "Records are archived from the following tables:"
      echo
      for TABLE in ${TABLES}
      do
        echo "    ${DATABASE}.${TABLE}"
      done
      echo
      echo "Options:"
      echo " -n dry run mode - pass --dry-run to pt-archiver"
      echo " -a no safe auto increment - pass --nosafe-auto-increment to pt-archiver"
      echo " -d db name"
      echo " -H db hostname"
      echo " -u db username"
      echo " -p db password"
      echo " -h (show help)"
      exit 0
      ;;
    n)
      DRY_RUN="--dry-run"
      ;;
    a)
      NOSAI="--nosafe-auto-increment"
      ;;
    d)
      DATABASE=${OPTARG}
      ;;
    H)
      HOSTPT=",h=${OPTARG}"
      HOST="-h ${OPTARG}"
      ;;
    u)
      USERPT=",u=${OPTARG}"
      USER="-u ${OPTARG}"
      ;;
    p)
      PASSPT=",p=${OPTARG}"
      PASS="-p${OPTARG}"
      ;;
    \?)
      echo "Invalid option: -$OPTARG" >&2
      exit 1
      ;;
    :)
      echo "Option -$OPTARG requires an argument." >&2
      exit 1
      ;;
  esac
done

echo
echo `date` "OpenStack Database Archiver starting.."
echo


echo `date` "Purging nova.instance_actions_events of deleted instance data"
# this is back to front (on delete if you can find a record in instances flagged for deletion)
# --where 'EXISTS(SELECT * FROM instance_actions, instances WHERE instance_actions.id=instance_actions_events.action_id AND instance_actions.instance_uuid=instances.uuid AND instances.deleted!=0)'

TABLE=instance_actions_events
SHADOW_TABLE="shadow_${TABLE}"
pt-archiver ${DRY_RUN} ${NOSAI} --statistics --sleep-coef 0.75 --progress 100 --commit-each --limit 10 \
  --source D=${DATABASE},t=${TABLE}${HOSTPT}${USERPT}${PASSPT} --no-check-charset  \
  --dest D=${DATABASE},t=${SHADOW_TABLE}${HOSTPT}${USERPT}${PASSPT} \
  --where 'EXISTS(SELECT * FROM instance_actions, instances WHERE instance_actions.id=instance_actions_events.action_id AND instance_actions.instance_uuid=instances.uuid AND instances.deleted!=0)'


for TABLE in ${FKTABLES}; do
  echo `date` "Purging nova.${TABLE} of deleted instance data"
  # this is back to front (on delete if you can find a record in instances flagged for deletion)
  # --where 'EXISTS(SELECT * FROM instances WHERE deleted!=0 AND uuid='${TABLE}'.instance_uuid)'
  # to delete where there is no active record:
  # --where 'NOT EXISTS(SELECT * FROM instances WHERE deleted=0 AND uuid='${TABLE}'.instance_uuid)'

  SHADOW_TABLE="shadow_${TABLE}"
  pt-archiver ${DRY_RUN} ${NOSAI} --statistics --sleep-coef 0.75 --progress 100 --commit-each --limit 10 \
    --source D=${DATABASE},t=${TABLE}${HOSTPT}${USERPT}${PASSPT} --no-check-charset  \
    --dest D=${DATABASE},t=${SHADOW_TABLE}${HOSTPT}${USERPT}${PASSPT} \
    --where 'EXISTS(SELECT * FROM instances WHERE deleted!=0 AND uuid='${TABLE}'.instance_uuid)'
done


for TABLE in ${TABLES}
do
  SHADOW_TABLE="shadow_${TABLE}"

  ACTIVE_RECORDS=`mysql ${HOST} ${USER} ${PASS} -B -e "select count(id) from ${DATABASE}.${TABLE} where deleted=0" | tail -1`
  DELETED_RECORDS=`mysql ${HOST} ${USER} ${PASS} -B -e "select count(id) from ${DATABASE}.${TABLE} where deleted!=0" | tail -1`

  LOCAL_ABORTS=`mysql ${HOST} ${USER} ${PASS} -B -e "SHOW STATUS LIKE 'wsrep_%'" | grep -e wsrep_local_bf_aborts -e wsrep_local_cert_failures`

	echo
	echo
  echo `date` "Archiving ${DELETED_RECORDS} records to ${SHADOW_TABLE} from ${TABLE}, leaving ${ACTIVE_RECORDS}"
  echo `date` "LOCAL_ABORTS before"
	echo ${LOCAL_ABORTS}

  pt-archiver ${DRY_RUN} ${NOSAI} --statistics --progress 100 --commit-each --limit 10 \
    --source D=${DATABASE},t=${TABLE}${HOSTPT}${USERPT}${PASSPT} \
    --dest D=${DATABASE},t=${SHADOW_TABLE}${HOSTPT}${USERPT}${PASSPT} \
    --ignore --no-check-charset --sleep-coef 0.75 \
    --where "deleted!=0"

  echo `date` "Finished archiving ${DELETED_RECORDS} to ${SHADOW_TABLE} from ${TABLE}"
  echo `date` "LOCAL_ABORTS before"
	echo ${LOCAL_ABORTS}
  LOCAL_ABORTS=`mysql ${HOST} ${USER} ${PASS} -B -e "SHOW STATUS LIKE 'wsrep_%'" | grep -e wsrep_local_bf_aborts -e wsrep_local_cert_failures`
  echo `date` "LOCAL_ABORTS after"
	echo ${LOCAL_ABORTS}
  echo
done

echo
echo `date` "OpenStack Database Archiver finished."
echo
