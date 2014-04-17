Bonding in UI/Nailgun
=====================

Abstract
--------

The NIC bonding allows you to aggregate multiple physical links to one link
to increase speed and provide fault tolerance.

Design docs
-----------

https://etherpad.openstack.org/p/fuel-bonding-design

Fuel Support
------------

The Puppet module L23network has support for OVS and native Linux bonding,
so we can use it for both NovaNetwork and Neutron deployments. Only Native
OVS bonding (Neutron only) is implemented in Nailgun now. Vlan splinters cannot
be used on bonds now. Three modes are supported now: 'active-backup',
'balance-slb', 'lacp-balance-tcp' (see nailgun.consts.OVS_BOND_MODES).

Deployment serialization
------------------------

Most detailed docs on deployment serialization for neutron are here:

1. http://docs.mirantis.com/fuel/fuel-4.0/reference-architecture.html#advanced-network-configuration-using-open-vswitch
2. https://etherpad.openstack.org/p/neutron-orchestrator-serialization

Changes related to bonding are in the “transformations” section:

1. "add-bond" section
::

  {
    "action": "add-bond",
    "name": "bond-xxx", # name is generated in UI
    "interfaces": [], # list of NICs; ex: ["eth1", "eth2"]
    "bridge": "br-xxx",
    "properties": [] # info on bond's policy, mode; ex: ["bond_mode=active-backup"]
  }

2. Instead of creating separate OVS bridges for every bonded NIC we need to create one bridge for the bond itself
::

  {
    "action": "add-br",
    "name": "br-xxx"
  }

REST API
--------

NodeNICsHandler and NodeCollectionNICsHandler are used for bonds creation,
update and removal. Operations with bonds and networks assignment are done in
single request fashion. It means that creation of bond and appropriate networks
reassignment is done using one request. Request parameters must contain
sufficient and consistent data for construction of new interfaces topology and
proper assignment of all node's networks.

Request/response data example::

  [
    {
      "name": "ovs-bond0", # only name is set for bond, not id
      "type": "bond",
      "mode": "balance-slb", # see nailgun.consts.OVS_BOND_MODES for modes list
      "slaves": [
        {"name": "eth1"}, # only “name” must be in slaves list
        {"name": "eth2"}],
      "assigned_networks": [
        {
          "id": 9,
          "name": "public"
        }
      ]
    },
    {
      "name": "eth0",
      "state": "up",
      "mac": "52:54:00:78:55:68",
      "max_speed": null,
      "current_speed": null,
      "assigned_networks": [
        {
          "id": 1,
          "name": "fuelweb_admin"
        },
        {
          "id": 10,
          "name": "management"
        },
        {
          "id": 11,
          "name": "storage"
        }
      ],
      "type": "ether",
      "id": 5
    },
    {
      "name": "eth1",
      "state": "up",
      "mac": "52:54:00:88:c8:78",
      "max_speed": null,
      "current_speed": null,
      "assigned_networks": [], # empty for bond slave interfaces
      "type": "ether",
      "id": 2
    },
    {
      "name": "eth2",
      "state": "up",
      "mac": "52:54:00:03:d1:d2",
      "max_speed": null,
      "current_speed": null,
      "assigned_networks": [], # empty for bond slave interfaces
      "type": "ether",
      "id": 1
    }
  ]

Following fields are required in request body for bond interface:
name, type, mode, slaves.
Following fields are required in request body for NIC:
id, type.

Nailgun DB
----------

Now we have separate models for bond interfaces and NICs: NodeBondInterface and
NodeNICInterface. Node's interfaces can be accessed through Node.nic_interfaces
and Node.bond_interfaces separately or through Node.interfaces (property,
read-only) all together.
Relationship between them (bond:NIC ~ 1:M) is expressed in “slaves” field in
NodeBondInterface model.
Two more new fields in NodeBondInterface are: “flags” and “mode”.
Bond's “mode” can accept values from nailgun.consts.OVS_BOND_MODES.
Bond's “flags” are not in use now. “type” property (read-only) indicates whether
it is a bond or NIC (see nailgun.consts.NETWORK_INTERFACE_TYPES).
