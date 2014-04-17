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

.. _openstack.yaml: https://github.com/stackforge/fuel-web/blob/master/nailgun/nailgun/fixtures/openstack.yaml
