#!/bin/bash
#
# Copyright 2016 Workday, Inc. All Rights Reserved.
#
# Author: Edgar Magana <edgar.magana@workday.com>
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
# This script decodes the information in /proc/cpuinfo and
# produces a human readable version displaying:
# - Total number of physical CPUs
# - Total number of logical CPUs
# - Model of the chipset
#

# Default linux file for CPU information
CPUFILE=/proc/cpuinfo

NUMPHY=`grep "physical id" $CPUFILE | sort -u | wc -l`
NUMLOG=`grep "processor" $CPUFILE | wc -l`

if [ $NUMPHY -eq 1 ]; then
    echo This system has one physical CPU,
else
    echo This system has $NUMPHY physical CPUs,
fi

if [ $NUMLOG -gt 1 ]; then
    echo and $NUMLOG logical CPUs
    NUMCORE=`grep "core id" $CPUFILE | sort -u | wc -l`
    if [ $NUMCORE -gt 1 ]; then
        echo For every physical CPU there are $NUMCORE cores.
    fi
    else
        echo and one logical CPU.
fi

echo -n The CPU is a `grep "model name" $CPUFILE | sort -u | cut -d : -f 2-`
echo " with`grep "cache size" $CPUFILE | sort -u | cut -d : -f 2-` cache"
