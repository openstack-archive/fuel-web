Creating roles
==============

Each release has its own role list which can be customized. A plain list of
roles is stored in the "roles" section of each release in the openstack.yaml_::

  roles:
    - controller
    - compute
    - cinder

The order in which the roles are listed here determines the order in which
they are displayed on the UI.

For each role in this list there should also be entry in "roles_metadata"
section. It defines role name, description and conflicts with other roles::

  roles_metadata:
    controller:
      name: "Controller"
      description: "..."
      conflicts:
        - compute
    compute:
      name: "Compute"
      description: "..."
      conflicts:
        - controller
    cinder:
      name: "Storage - Cinder LVM"
      description: "..."

"conflicts" section should contain a list of other roles that cannot be placed
on the same node. In this example, "controller" and "compute" roles cannot be
combined.

Roles restrictions
------------------

You should take the following restrictions for the role into consideration:

#. Controller

   * There should be at least one controller.

   * If we are using simple multinode mode, then we cannot add more than one controller.

   * In HA mode, we can add as much as possible controllers, though it is recommended to add at least 3.

   * Controller role cannot be combined with compute.

   * Not enough deployed controllers - deployed cluster requires at least 1 deployed controller.

#. Compute

  * It is recommended to have at least one compute in non-vCenter env (https://bugs.launchpad.net/fuel/+bug/1381613 : note that this is a bug in UI and not yaml-specific).

  * Computes cannot be combined with controllers.

  * Computes cannot be added if vCenter is chosen as a hypervisorю

#. Cinder

  * It is impossible to add Cinder nodes to an environment with Ceph RBD.

  * At least one Cinder node is recommended if 'Cinder LVM over iSCSI' is turned on in the Settings
    tab of the Fuel web UI.

#. MongoDB

  * Cannot be added to already deployed environment.

  * Can be added only if Ceilometer is enabled.

  * Cannot be combined with Ceph OSD and Compute.

  * For a simple mode, there should be only 1 mongo node. for HA, there should be 3.

  * It is not allowed to choose MongoDB role for a node if external MongoDB setup is used.

#. Zabbix

  * Only available in experimental ISO.

  * Cannot be combined with any other roles.

  * Only one Zabbix node can be assigned in an environment.

#. Ceph

  * Cannot be used with Mongo and Zabbix.

  * Ceph nodes can not be added to the env with ceph settings are turned off.

  * Ceph cannot be added if vCenter is chosen as a hypervisor and volumes_ceph setting is False.

#. Ceilometer

  * Either a node with MongoDB role or external MongoDB turned on is required .


.. _openstack.yaml: https://github.com/stackforge/fuel-web/blob/master/nailgun/nailgun/fixtures/openstack.yaml
