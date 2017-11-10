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

"""
What is this ?!
---------------

This script is designed to monitor VMs resource utilization

WorkFlow
--------

1) List all domains at the host via libvirt API
2) Spawn a separate thread for each domain for periodic check of disk usage
3) Spawn a separate thread for each domain for periodic check of memory usage
4) Spawn a separate thread for each domain for periodic check of cpu usage
5) Spawn a separate thread for checking of total numbers for host
6) Wait and read log messages with stats...

How to stop "monitoring"
------------------------

Just call Ctrl+C (KeyboardInterrupt) and the script should gracefully stop
all the threads and exit.

How to configure
----------------

The script accepts one input argument - the patch to a configuration file in
a JSON format.
All options are optional (have default values), so configuration file is
optional as well.

Options:

  * debug
      bool, if True the logger will use DEBUG level or INFO level if False.
      Defaults to False
  * connection
      str, URI of libvirt to connect
      Defaults to "qemu:///system"
  * disk_getinfo_method
      str, The way to obtain an information about the disk. There are 3
      options available:
        - "qemu" - using `qemu-img info` command
        - "virsh" - via pulling volume pools and volumes in them by libvirt
           API. like it is done in `virsh pool-list` and `virsh vol-info`
           commands
        - "guestfs" - mount all the disks and checks the actual size
          (experimental, not checked actually)
      Defaults to "qemu"
  * host_check_interval
      float, The interval to sleep between checking stats
      Defaults to 5
  * disk_check_interval
      float, The interval to sleep between updating stats about disk usage
      of a single VM.
      Defaults to 10
  * memory_check_interval
      float, The interval to sleep between updating stats about ram usage
      of a single VM.
      Defaults to 5
  * cpu_check_interval
      float, The interval to sleep between updating stats about CPU usage
      of a single VM.
      Defaults to 1
  * host_disk_utilization_alert
      float, the number between 0 to 100. The achievement of the host's disk
      usage to send alert about critical situation
      Defaults to 80
  * vm_disk_utilization_alert
      float, the number between 0 to 100. The achievement of the VM's disk
      usage to send alert about critical situation
      Defaults to host_disk_utilization_alert value
  * host_memory_utilization_alert
      float, the number between 0 to 100. The achievement of the host's RAM
      usage to send alert about critical situation
      Defaults to 80
  * vm_memory_utilization_alert
      float, the number between 0 to 100. The achievement of the VM's RAM
      usage to send alert about critical situation
      Defaults to host_memory_utilization_alert value

"""

import logging
import sys
import subprocess
import time
import threading
import xml.etree.ElementTree

import json
import libvirt


LOG = logging.getLogger("vm-stats")


def set_config_defaults(config):
    """Setup all default for config options."""
    config.setdefault("debug", False)
    config.setdefault("connection", "qemu:///system")
    config.setdefault("disk_getinfo_method", "qemu")
    # intervals
    config.setdefault("host_check_interval", 5)
    config.setdefault("disk_check_interval", 10)
    config.setdefault("memory_check_interval", 5)
    config.setdefault("cpu_check_interval", 1)
    # alerts
    config.setdefault("host_disk_utilization_alert", 80)
    config.setdefault("vm_disk_utilization_alert",
                      config["host_disk_utilization_alert"])
    config.setdefault("host_memory_utilization_alert", 80)
    config.setdefault("vm_memory_utilization_alert",
                      config["host_memory_utilization_alert"])
    return config


class Disk(object):

    _VIRSH_VOLUME_CACHE = {}

    def __init__(self, vm, dump, connection, config):
        self._conn = connection
        self._config = config

        self.vm = vm
        self.dump = dump
        self.path = dump.find("source").get("file")

        # self.target = dump.find("target")

    def _get_info_from_qemu_img(self):
        output = subprocess.check_output(["qemu-img", "info", self.path])
        allocation = None
        capacity = None

        for line in output.splitlines():
            if line.startswith("virtual size"):
                # it looks like `virtual size: 4.0G (4294967296 bytes)`
                _w1, size, _w2 = line.rsplit(" ", 2)
                allocation = int(size.replace("(", ""))
            elif line.startswith("disk size"):
                size = line.split(" ")[2]
                try:
                    capacity = float(size)
                except ValueError:
                    from oslo_utils import strutils
                    capacity = strutils.string_to_bytes("%sB" % size,
                                                        return_int=True)

        if allocation is None or capacity is None:
            raise Exception("Failed to parse output of `qemu-img info %s`." %
                            self.path)

        return capacity, allocation

    def _get_info_from_virsh_vol_info(self):
        # use the class level cache to not load all pools and volumes for each
        # disk
        cache = self.__class__._VIRSH_VOLUME_CACHE
        if self.path not in cache:
            # try to load all volumes
            for pool in self._conn.listAllStoragePools():
                for volume in pool.listAllVolumes():
                    cache[self.path] = volume

        # it should appear after load
        if self.path not in cache:
            raise Exception("Failed to find %s volume." % self.path)

        _something, capacity, allocation = cache[self.path].info()
        return capacity, allocation

    def _get_info_from_guestfs(self):
        import guestfs

        capacity = 0
        allocation = 0

        g = guestfs.GuestFS()
        g.add_drive_opts(self.path, format="raw", readonly=1)
        g.launch()
        file_systems = g.list_filesystems()
        for fs in file_systems:
            if fs[1] not in ["", "swap", "unknown"]:
                g.mount(fs[0], "/")
                st = g.statvfs("/")
                capacity += (st.f_blocks * st.f_frsize)
                allocation += (st.f_blocks - st.f_bfree) * st.f_frsize
                g.umount_all()
        g.close()
        return capacity, allocation

    def info(self):
        LOG.debug("Fetching info of %s disk." % self.path)

        if self._config["disk_getinfo_method"] == "guestfs":
            return self._get_info_from_guestfs()
        elif self._config["disk_getinfo_method"] == "virsh":
            return self._get_info_from_virsh_vol_info()
        else:
            return self._get_info_from_qemu_img()


class VM(object):
    def __init__(self, domain, connection, config):
        self._conn = connection
        self._config = config

        self.id = domain.ID()
        self.uuid = domain.UUID()
        self.name = domain.name()
        self.dump = xml.etree.ElementTree.fromstring(domain.XMLDesc())
        self._disks = None

        # leave the original object just in case
        self._domain = domain

    @property
    def disks(self):
        if self._disks is None:
            self._disks = []
            for disk in self.dump.findall(".//disk"):
                if disk.get("device") != "disk" or disk.get("type") != "file":
                    continue
                self._disks.append(Disk(self, disk, self._conn, self._config))
        return self._disks

    def memory_utilization(self):
        stats = self._domain.memoryStats()
        total = stats["actual"]
        used = total - stats["available"]
        return total, used

    def cpu_utilization(self):
        total = self._domain.getCPUStats(total=True)[0]
        # The statistics are reported in nanoseconds.
        return total["cpu_time"] / 1000000000.


class Host(object):

    def __init__(self, config):
        conn = libvirt.openReadOnly(config["connection"])
        if conn is None:
            raise Exception("Failed to open connection to %s." %
                            config["connection"])
        self._config = config
        self._conn = conn

        self.vms = []
        self._stats = {}
        for domain_id in (self._conn.listDomainsID() or []):
            domain = self._conn.lookupByID(domain_id)
            self.vms.append(VM(domain, self._conn, config))
            self._stats[self.vms[-1].uuid] = {}

        LOG.info("Find %s active VMs at the host." % len(self.vms))
        LOG.debug("The list of VMs: '%s'." %
                  "', '".join(vm.name for vm in self.vms))

        self._disks_stats = {}
        self._memory_stats = {}
        self._cpu_stats = {}

        self._stop_event = threading.Event()

    def _vm_disk_utilization(self, vm, interval):
        while not self._stop_event.isSet():
            total_c = 0
            total_a = 0
            for disk in vm.disks:
                try:
                    capacity, allocation = disk.info()
                except:
                    if LOG.level == logging.DEBUG:
                        LOG.exception("Error occurred while obtaining info "
                                      "about disk (path=%s ; vm=%s)." %
                                      (disk.path, vm.name))
                    continue
                usage = capacity * 100.0 / allocation
                LOG.debug("%(vm)s uses %(usage).4f%% of the disk %(file)s." % {
                    "vm": vm.name,
                    "usage": usage,
                    "file": disk.path
                })

                if usage >= self._config["vm_disk_utilization_alert"]:
                    LOG.critical("The VM %s uses too much (%.4f%%) of it's "
                                 "disk %s!" % (vm.name, usage, disk.path))

                total_c += capacity
                total_a += allocation
            self._stats[vm.uuid]["disks_capacity"] = total_c
            self._stats[vm.uuid]["disks_allocation"] = total_a
            time.sleep(interval)

    def _vm_memory_utilization(self, vm, interval):
        while not self._stop_event.isSet():
            total, used = vm.memory_utilization()
            usage = used * 100.0 / total
            LOG.debug("%(vm)s uses %(usage).4f%% of memory." % {
                "vm": vm.name,
                "usage": usage
            })
            if usage >= self._config["vm_memory_utilization_alert"]:
                LOG.critical("The VM %s uses too much (%.4f%%) of it's "
                             "memory!" % (vm.name, usage))
            self._stats[vm.uuid]["total_ram"] = total
            self._stats[vm.uuid]["used_ram"] = used
            time.sleep(interval)

    def _vm_cpu_utilization(self, vm, interval):
        cpu_time_0 = None
        while not self._stop_event.isSet():
            cpu_time = vm.cpu_utilization()
            if cpu_time_0 is not None:
                usage = (100.0 * (cpu_time - cpu_time_0) / interval)
                LOG.debug("%(vm)s uses %(usage).4f%% of CPU." % {
                    "vm": vm.name,
                    "usage": usage
                })
            cpu_time_0 = cpu_time
            time.sleep(interval)

    def _check_resources(self):
        """Check Disk, RAM, CPU utilization of the whole host based on the
        stats from VMs and alert if necessary."""
        while not self._stop_event.isSet():
            disks_capacity = sum(
                [s.get("disks_capacity", 0) for s in self._stats.values()])
            disks_allocation = sum(
                [s.get("disks_allocation", 0) for s in self._stats.values()])
            if disks_allocation != 0:
                disk_usage = disks_capacity * 100.0 / disks_allocation
            else:
                # it is not loaded yet or no vms
                disk_usage = 0
            if disk_usage >= self._config["host_disk_utilization_alert"]:
                LOG.critical("Host uses too much (%.4f%%) of it's disk!" %
                             disk_usage)
            else:
                LOG.info("Host uses %.4f%% of it's disk." % disk_usage)

            total_ram = sum(
                [s.get("total_ram", 0) for s in self._stats.values()])
            used_ram = sum(
                [s.get("used_ram", 0) for s in self._stats.values()])

            if disks_allocation != 0:
                ram_usage = used_ram * 100.0 / total_ram
            else:
                # it is not loaded yet or no vms
                ram_usage = 0

            if ram_usage >= self._config["host_memory_utilization_alert"]:
                LOG.critical("Host uses too much (%.4f%%) of it's memory!" %
                             ram_usage)
            else:
                LOG.info("Host uses %.4f%% of it's memory." % ram_usage)

            time.sleep(self._config["host_check_interval"])

    def watch(self):

        workers = []

        for vm in self.vms:
            disk_t = threading.Thread(
                target=self._vm_disk_utilization,
                kwargs={"vm": vm,
                        "interval": self._config["disk_check_interval"]})
            disk_t.start()
            workers.append(disk_t)

            memory_t = threading.Thread(
                target=self._vm_memory_utilization,
                kwargs={"vm": vm,
                        "interval": self._config["memory_check_interval"]})
            memory_t.start()
            workers.append(memory_t)

            cpu_t = threading.Thread(
                target=self._vm_cpu_utilization,
                kwargs={"vm": vm,
                        "interval": self._config["cpu_check_interval"]})
            cpu_t.start()
            workers.append(cpu_t)

        checker_t = threading.Thread(target=self._check_resources)
        checker_t.start()

        try:
            while True:
                time.sleep(.1)
        except KeyboardInterrupt:
            self._stop_event.set()
            for worker in workers:
                worker.join()
            checker_t.join()


def main():
    if len(sys.argv) not in (1, 2):
        print("The script expects one argument - a path to config in json/yaml"
              " format.")
        exit(1)
    elif len(sys.argv) == 2:
        if sys.argv[1] in ("--help", "help"):
            print(__doc__)
            exit(0)

        try:
            with open(sys.argv[1]) as f:
                config = json.loads(f)
        except:
            print("Failed to load json from %s." % sys.argv[1])
            raise
    else:
        config = {}
    config = set_config_defaults(config)

    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    LOG.addHandler(handler)
    if config["debug"]:
        LOG.setLevel(logging.DEBUG)
    else:
        LOG.setLevel(logging.INFO)

    LOG.info("Loaded configuration:\n%s" % json.dumps(config, indent=4))

    host = Host(config)
    host.watch()


if __name__ == "__main__":
    main()
