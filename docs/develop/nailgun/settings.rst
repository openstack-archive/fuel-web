Extending OpenStack Settings
============================

Each release has a list of OpenStack settings that can be customized.
The settings configuration is stored in the "attributes_metadata.editable"
release section in the openstack.yaml_ file.

Settings are divided into groups:

* access
* additional_components
* common
* vlan_splinters
* syslog
* storage

Each group should have a "metadata" section with the following attributes::

  metadata:
    toggleable: true
    enabled: false
    weight: 40

* *toggleable* defines an ability to enable/disable the whole setting group
  on UI (checkbox control is presented near a setting group label)
* *enabled* indicates whether the group is checked on the UI
* *weight* defines the order in which this group is displayed on the tab.
  This attribute is desirable

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
        depends:
          - "settings:common.auto_assign_floating_ip.value": true
        conflicts:
          - "settings:common.use_cow_images.value": true
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
* *depends* list defines setting dependencies on some environment property
  (mode, networking, etc) or any other setting from release setting list.
  For example, the "Murano" setting from the "additional_components" group
  can not be activated for an environment with Neutron networking.
  Any setting with an unsatisfied dependency is disabled on UI.
  Setting dependencies are declared by a list of conditions of the
  following format::

  "<model_name>:<model_attribute_path>": <model_attribute_value>

* *conflicts* defines a list of settings that can not be activated together
  with the current setting. For example, "Cinder LVM over iSCSI for volumes"
  and "Ceph RBD for volumes (Cinder)" settings from the "storage"
  setting group can not be activated at the same time.
  Conflicts is a list of conditions of the same format as setting
  dependencies
* *description* section should also contain information about setting
  restrictions (dependencies, conflicts)
* *values* list is needed for settings of "radio" type to declare its
  possible values. Options from "values" list also support dependencies
  and conflcits declaration.

.. _openstack.yaml: https://github.com/stackforge/fuel-web/blob/master/nailgun/nailgun/fixtures/openstack.yaml