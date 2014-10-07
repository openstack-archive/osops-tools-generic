ansible-playbooks
=================

Go Daddy Ansible playbooks for managing OpenStack infrastructure.

Also available publically at https://github.com/godaddy/openstack-ansible

This assumes your baseline Ansible config is at `/etc/ansible`, and this repo is cloned
to `/etc/ansible/playbooks`  (Specifically, the playbooks assume the path to the tasks directory is `/etc/ansible/playbooks/tasks`,
so if you are cloning this repo somewhere else, you'll need to adjust that.)

Patches/comments/complaints welcomed and encouraged!  Create an issue or PR here.

Usage Details
-------------

Playbooks are "shebanged" with `#!/usr/bin/env ansible-playbook --forks 50`, so you can actually 
just run them directly from the command line.

We have the concept of "worlds", which correspond to dev, test, prod, etc., servers.  We use
the world teminology to avoid confusion with the Puppet environment setting (which, for us, 
corresponds to a branch in our [openstack-puppet](https://github.com/godaddy/openstack-puppet) repo.)  So when you see references to the world
variable, that's what it is.  Right now only a couple playbooks utilize that, so for the most
part you can probably use these without worrying about defining a world variable.

puppet-run.yaml and r10k-deploy.yaml are fairly specific to our environment, and are probably
mostly irrelevant unless you're also using our openstack-puppet repo for Puppet configuration.

Basic usage for the other playbooks follows.

### template-prestage.yaml

This one is really cool, complements of [krislindgren](http://github.com/krislindgren).  It sets up a 
BitTorrent swarm, seeded by the machine running Glance, to distribute a Glance image out to any number
of nova-compute nodes very quickly.  So when we roll new gold images each month, we can use this to
"push" them out to all compute nodes, and avoid the first provision penalty of waiting for the image
to transfer the first time.

Caveats:
* Only works when the Glance backend is on a traditional (local or network-based) filesystem.  Almost
certainly this does not work, and may not even make sense, for Swift-backed Glance.
* Firewalls or other traffic filters need to allow the BitTorrent ports through, and among, the Glance
server and all compute nodes.
* Assumes Glance images are stored at `/var/lib/glance/images` on the Glance server.
* There are some situations where this cannot be run multiple times, if the tracker or othe BitTorrent
processes are still running.  So use caution, and YMMV.
* This is done completely outside the scope of Glance and Nova.  There is no Keystone authentication or
access controls.  You must have ssh and sudo access to all machines involved for this to work.

Usage:

    ./template-prestage.yaml -k -K -e "image_uuid=<uuid> image_sha1=<sha1> image_md5=<md5> tracker_host=<glance server> hosts_to_update=<compute host group>"

* _image_uuid_: UUID of the image to prestage (from `nova image-list` or `glance image-list`)
* _image_sha1_: SHA1 sum of the image_uuid (this can be gotten by running: `echo -n "<image_uuid>" | sha1sum | awk '{print $1}'`  on any Linux box)
* _image_md5_: MD5 sum of the image file itsemf (this can be gotten by running: `md5sum /var/lib/glance/images/<image_uuid> | awk '{print $1}'` on the Glance server
* _tracker_host_: This is the Glance server host that runs the tracker
* _hosts_to_update_: This is the host group to place the image onto (a list of compute nodes)

### copy-hiera-eyaml-keys.yaml

Copies public and private keys for hiera-eyaml from the source/ansible client machine, to hosts, at
`/etc/pki/tls/private/hiera-eyaml-{public,private}_key.pkcs.pem`

    ./copy-hiera-eyaml-keys.yaml -k -K -e "srcdir=<srcdir> hosts=<host group>"

* _srcdir_: Source directory on the ansible client machine where the hiera-eyaml-public_key.pkcs7.pem and hiera-eyaml-private_key.pkcs7.pem keys can be found

### patching.yaml

This is a simple playbook to run `yum -y update --skip-broken` on all machines.

    ./patching.yaml -k -K -e "hosts=<host group>"

This also runs the remove-old-kernels.yaml task first, which removes any kernel packages from the
system which are not 1) the currently running kernel, nor, 2) the default boot kernel in GRUB.

### updatepackages.yaml

Similar to patching.yaml, but this one allows for a specification of exactly which package(s) to update.

    ./updatepackages.yaml -k -K -e "puppet=<true|false> package=<package spec> hosts=<host group>"

* _puppet_: If true, will also run the puppet-run.yaml task after updating the packages.  Default false.
* _package spec_: Specification for what packages to update, wildcards are valid.  Default '*'

### restartworld.yaml

Restarts some (or all) openstack services on hosts.  Note that this uses the `tools/restartworld.sh` script
from the [godaddy/openstack-puppet](https://github.com/godaddy/openstack-puppet) repo, so you may want to look at that before trying to use this playbook.

This is also somewhat specific to our environment, as far as how we group services together (most of 
them run on the "app" class of server.)  So results and usefulness may vary.

    ./restartworld.yaml -k -K -e "class=<server class> hosts=<host group> service=<service class>"

* _class_: Server class to define what services to restart.  Recognized options are app, network, and compute.  See the `restartworld.sh` script referenced above for which services are on which class of server.  You may want to define a group var for this (that's what we did) to automatically map servers to their appropriate server class value.
* _hosts_: Hosts on which to perform the service restarts
* _service class_: Generally, the OpenStack project name for the services to restart.  Recognized options are nova,keystone,glance,ceilometer,heat,neutron,spice,els,world (where "world" means all services.)


