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
    min: 1
    max: 3

* *label* is a setting title that is displayed on UI
* *weight* defines the order in which this setting is displayed in its group.
  This attribute is desirable
* *type* defines the type of UI control to use for the setting.
  The following types are supported:

  * *text* - single line input
  * *password* - password input
  * *textarea* - multiline input
  * *checkbox* - multiple-options selector
  * *radio* - single-option selector
  * *select* - drop-down list
  * *hidden* - invisible input
  * *file* - file contents input
  * *text_list* - multiple sigle line text inputs
  * *textarea_list* - multiple multiline text inputs

* *regex* section is applicable for settings of "text" type. "regex.source"
  is used when validating with a regular expression. "regex.error" contains
  a warning displayed near invalid field
* *restrictions*: see restrictions_.
* *description* section should also contain information about setting
  restrictions (dependencies, conflicts)
* *values* list is needed for settings of "radio" or "select" type to declare
  its possible values. Options from "values" list also support dependencies
  and conflcits declaration.
* *min* is actual for settings of "text_list" or "textarea_list" type
  to declare a minimum input list length for the setting
* *max* is actual for settings of "text_list" or "textarea_list" type
  to declare a maximum input list length for the setting

.. _restrictions:

Restrictions
------------

Restrictions define when settings and setting groups should be available.
Each restriction is defined as a *condition* with optional *action*, *message*
and *strict*::

    restrictions:
      - condition: "settings:common.libvirt_type.value != 'kvm'"
        message: "KVM only is supported"
      - condition: "not ('experimental' in version:feature_groups)"
        action: hide

* *condition* is an expression written in `Expression DSL`_. If returned value
  is true, then *action* is performed and *message* is shown (if specified).

* *action* defines what to do if *condition* is satisfied. Supported values
  are "disable", "hide" and "none". "none" can be used just to display
  *message*. This field is optional (default value is "disable").

* *message* is a message that is shown if *condition* is satisfied. This field
  is optional.

* *strict* is a boolean flag which specifies how to handle non-existent keys
  in expressions. If it is set to true (default value), exception is thrown in
  case of non-existent key. Otherwise values of such keys have null value.
  Setting this flag to false is useful for conditions which rely on settings
  provided by plugins::

    restrictions:
      - condition: "settings:other_plugin == null or settings:other_plugin.metadata.enabled != true"
        strict: false
        message: "Other plugin must be installed and enabled"

There are also short forms of restrictions::

    restrictions:
      - "settings:common.libvirt_type.value != 'kvm'": "KVM only is supported"
      - "settings:storage.volumes_ceph.value == true"

.. _Expression DSL:

Expression Syntax
-----------------

Expression DSL can describe arbitrarily complex conditions that compare fields
of models and scalar values.

Supported types are:

* Number (123, 5.67)

* String ("qwe", 'zxc')

* Boolean (true, false)

* Null value (null)

* ModelPath (settings:common.libvirt_type.value, cluster:net_provider)

ModelPaths consist of a model name and a field name separated by ":". Nested
fields (like in settings) are supported, separated by ".". Models available for
usage are "cluster", "settings", "networking_parameters" and "version".

Supported operators are:

* "==". Returns true if operands are equal::

    settings:common.libvirt_type.value == 'qemu'

* "!=". Returns true if operands are not equal::

    cluster:net_provider != 'neutron'

* "in". Returns true if the right operand (Array or String) contains the left
  operand::

    'ceph-osd' in release:roles

* Boolean operators: "and", "or", "not"::

    cluster:mode == "ha_compact" and not (settings:common.libvirt_type.value == 'kvm' or 'experimental' in version:feature_groups)

Parentheses can be used to override the order of precedence.

.. _openstack.yaml: https://github.com/openstack/fuel-web/blob/master/nailgun/nailgun/fixtures/openstack.yaml
