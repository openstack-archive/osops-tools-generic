# Neutron Orphan Cleanup Tools

Provides a simple set of scripts to aid in the cleanup of orphaned resources in Neutron. Current scripts include:

 * list_orhpans.py - List orphaned networks, subnets, routers and floating IPs.
 * delete_orphan_floatingips.py - Cleanup floating IPs without any associated ports.
 * delete_tenantless_floatingips.py - Cleanup floating IPs without an associated tenant / project.


### Installation

Scripts work with Python 2.7 or newer including Python 3. It is suggested you install any Python scripts in a seperate Python VirtualEnv to prevent spoiling your system's Python environment.

Create a new VirtualEnv and assume the VirtualEnv

```
virtualenv orphan_tools
source orphan_tools/bin/activate
```

Install dependencies

`pip install -r requirements.txt`


### Usage

Export OpenStack credentials as environment variables

```
export OS_USERNAME=test
export OS_PASSWORD=mys3cr3t
export OS_AUTH-URL=https://controller:5000/v2.0
export OS_TENANT_NAME=test
export OS_REGION_NAME=my_region
```

List orphaned Neutron resources

`python list_orphans.py`

It is recommended before you delete orphaned resources that you do a dry run and check the script proposes to delete the resources you expect

`python delete_orphan_floatingips.py --dry-run`

Once you are happy you'd like to delete the items returned by the dry run remove the --dry-run flag to perform the deletion

`python delete_orphan_floatingips.py`
