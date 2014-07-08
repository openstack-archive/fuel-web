Extending OpenStack Settings
============================

Each release has a list of OpenStack settings that can be customized.
The settings configuration is stored in the "attributes_metadata.editable"
release section in the openstack.yaml_ file.

Settings are divided into groups. Each group should have a "metadata" section
with the following attributes::

  metadata:
    toggleable: true
    enabled: false
    weight: 40

* *toggleable* defines an ability to enable/disable the whole setting group
  on UI (checkbox control is presented near a setting group label)
* *enabled* indicates whether the group is checked on the UI
* *weight* defines the order in which this group is displayed on the tab.
* *restrictions*: see restrictions_.

Other sections of a setting group represent separate settings. A setting
structure includes the following attributes::

  syslog_transport:
    value: "tcp"
    label: "Syslog transport protocol"
    description: ""
    weight: 30
    type: "radio"
    values:
      - data: "udp"
        label: "UDP"
        description: ""
        restrictions:
          - "cluster:net_provider != 'neutron'"
      - data: "tcp"
        label: "TCP"
        description: ""
    regex:
      source: "^[A-z0-9]+$"
      error: "Invalid data"
    depends:
      - "cluster:net_provider": "neutron"
    conflicts:
      - "settings:storage.volumes_lvm.value": true

* *label* is a setting title that is displayed on UI
* *weight* defines the order in which this setting is displayed in its group.
  This attribute is desirable
* *type* defines the type of UI control to use for the setting
* *regex* section is applicable for settings of "text" type. "regex.source"
  is used when validating with a regular expression. "regex.error" contains
  a warning displayed near invalid field
* *restrictions*: see restrictions_.
* *description* section should also contain information about setting
  restrictions (dependencies, conflicts)
* *values* list is needed for settings of "radio" type to declare its
  possible values. Options from "values" list also support dependencies
  and conflcits declaration.

.. _restrictions:

Restrictions
------------

Restrictions define when settings and setting groups should be available.
Restrictions consts of *condition*, *action* and *message*::

    restrictions:
      - condition: "settings:common.libvirt_type.value != 'kvm'"
        message: "KVM is not supported with this feature"
      - condition: "not ('experimental' in version:feature_groups)"
        action: hide

* *condition* is an expression written in expression DSL. If returned value
  is true, then *action* is performed and *message* is shown (if specified).

* *action* defines what to do if *condition* is satisfied. Supported values
  are "disable", "hide" and "none". "none" can be used just to display
  *message*. This field is optional (default value is "disable").

* *message* is a message that is shown if *condition* is satisfied. This field
  is optional.

There are also short forms of restrictions::

    restrictions:
      - "settings:common.libvirt_type.value != 'kvm'": "KVM is not supported"
      - "settings:storage.volumes_ceph.value == true"

.. _expression_syntax:

Expression Syntax
-----------------

111

.. _openstack.yaml: https://github.com/stackforge/fuel-web/blob/master/nailgun/nailgun/fixtures/openstack.yaml