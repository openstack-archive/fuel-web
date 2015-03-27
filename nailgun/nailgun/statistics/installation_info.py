#    Copyright 2014 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from nailgun.db.sqlalchemy.models import NeutronConfig
from nailgun.db.sqlalchemy.models import NovaNetworkConfig
from nailgun.objects import ClusterCollection
from nailgun.objects import MasterNodeSettings
from nailgun.objects import NodeCollection
from nailgun.settings import settings
from nailgun import utils


class InstallationInfo(object):
    """Collects info about Fuel installation
    Master nodes, clusters, networks, e.t.c.
    Used for collecting info for fuel statistics
    """

    attributes_white_list = (
        # ((path, to, property), 'map_to_name', transform_function)
        (('common', 'libvirt_type', 'value'), 'libvirt_type', None),
        (('common', 'debug', 'value'), 'debug_mode', None),
        (('common', 'use_cow_images', 'value'), 'use_cow_images', None),
        (('common', 'auto_assign_floating_ip', 'value'),
         'auto_assign_floating_ip', None),
        (('common', 'nova_quota', 'value'), 'nova_quota', None),
        (('common', 'resume_guests_state_on_host_boot', 'value'),
         'resume_guests_state_on_host_boot', None),

        (('corosync', 'verified', 'value'), 'corosync_verified', None),

        (('public_network_assignment', 'assign_to_all_nodes', 'value'),
         'assign_public_to_all_nodes', None),
        (('syslog', 'syslog_transport', 'value'), 'syslog_transport', None),
        (('provision', 'method', 'value'), 'provision_method', None),
        (('kernel_params', 'kernel', 'value'), 'kernel_params', None),

        (('external_mongo', 'mongo_replset', 'value'),
         'external_mongo_replset', bool),
        (('external_ntp', 'ntp_list', 'value'), 'external_ntp_list', bool),

        (('repo_setup', 'repos', 'value'), 'repos', bool),

        (('storage', 'volumes_lvm', 'value'), 'volumes_lvm', None),
        (('storage', 'iser', 'value'), 'iser', None),
        (('storage', 'volumes_ceph', 'value'), 'volumes_ceph', None),
        (('storage', 'images_ceph', 'value'), 'images_ceph', None),
        (('storage', 'images_vcenter', 'value'), 'images_vcenter', None),
        (('storage', 'ephemeral_ceph', 'value'), 'ephemeral_ceph', None),
        (('storage', 'objects_ceph', 'value'), 'objects_ceph', None),
        (('storage', 'osd_pool_size', 'value'), 'osd_pool_size', None),

        (('neutron_mellanox', 'plugin', 'value'), 'mellanox', None),
        (('neutron_mellanox', 'vf_num', 'value'), 'mellanox_vf_num', None),

        (('additional_components', 'sahara', 'value'), 'sahara', None),
        (('additional_components', 'murano', 'value'), 'murano', None),
        (('additional_components', 'heat', 'value'), 'heat', None),
        (('additional_components', 'ceilometer', 'value'), 'ceilometer', None),
        (('additional_components', 'mongo', 'value'), 'mongo', None),

        (('workloads_collector', 'enabled', 'value'),
         'workloads_collector_enabled', None),
    )

    def fuel_release_info(self):
        versions = utils.get_fuel_release_versions(settings.FUEL_VERSION_FILE)
        if settings.FUEL_VERSION_KEY not in versions:
            versions[settings.FUEL_VERSION_KEY] = settings.VERSION
        return versions[settings.FUEL_VERSION_KEY]

    def get_network_configuration_info(self, cluster):
        network_config = cluster.network_config
        result = {}
        if isinstance(network_config, NovaNetworkConfig):
            result['net_manager'] = network_config.net_manager
            result['fixed_networks_vlan_start'] = \
                network_config.fixed_networks_vlan_start
            result['fixed_network_size'] = network_config.fixed_network_size
            result['fixed_networks_amount'] = \
                network_config.fixed_networks_amount
        elif isinstance(network_config, NeutronConfig):
            result['segmentation_type'] = network_config.segmentation_type
            result['net_l23_provider'] = network_config.net_l23_provider
        return result

    def get_clusters_info(self):
        clusters = ClusterCollection.all()
        clusters_info = []
        for cluster in clusters:
            release = cluster.release
            nodes_num = NodeCollection.filter_by(
                None, cluster_id=cluster.id).count()
            cluster_info = {
                'id': cluster.id,
                'nodes_num': nodes_num,
                'release': {
                    'os': release.operating_system,
                    'name': release.name,
                    'version': release.version
                },
                'mode': cluster.mode,
                'nodes': self.get_nodes_info(cluster.nodes),
                'node_groups': self.get_node_groups_info(cluster.node_groups),
                'status': cluster.status,
                'attributes': self.get_attributes(cluster.attributes.editable),
                # 'vmware_attributes': self.get_attributes(cluster.vmware_attributes.editable),
                'net_provider': cluster.net_provider,
                'fuel_version': cluster.fuel_version,
                'is_customized': cluster.is_customized,
                'network_configuration': self.get_network_configuration_info(
                    cluster),
                'installed_plugins': self.get_cluster_plugins_info(cluster)
            }
            clusters_info.append(cluster_info)
        return clusters_info

    def get_cluster_plugins_info(self, cluster):
        plugins_info = []
        for plugin_inst in cluster.plugins:
            plugin_info = {
                "id": plugin_inst.id,
                "name": plugin_inst.name,
                "version": plugin_inst.version,
                "releases": plugin_inst.releases,
                "fuel_version": plugin_inst.fuel_version,
                "package_version": plugin_inst.package_version,
            }
            plugins_info.append(plugin_info)

        return plugins_info

    def get_attributes(self, attributes):
        result = {}
        for path, map_to_name, func in self.attributes_white_list:
            attr = attributes
            try:
                for p in path:
                    attr = attr[p]
                if func is not None:
                    attr = func(attr)
                result[map_to_name] = attr
            except (KeyError, TypeError):
                pass
        return result

    def get_vmware_attributes(self, cluster):
        attrs = cluster.vmware_attributes
        # print "#### attributes", cluster.attributes.editable
        print "#### vmware_attributes", cluster
        result = {}
        # if isinstance(network_config, NovaNetworkConfig):
        #     result['net_manager'] = network_config.net_manager
        #     result['fixed_networks_vlan_start'] = \
        #         network_config.fixed_networks_vlan_start
        #     result['fixed_network_size'] = network_config.fixed_network_size
        #     result['fixed_networks_amount'] = \
        #         network_config.fixed_networks_amount
        # elif isinstance(network_config, NeutronConfig):
        #     result['segmentation_type'] = network_config.segmentation_type
        #     result['net_l23_provider'] = network_config.net_l23_provider


        # {
        #     u'value': {
        #         u'glance': {u'vcenter_username': u'', u'datacenter': u'', u'vcenter_host': u'', u'vcenter_password': u'', u'datastore': u''},
        #         u'availability_zones': [{u'vcenter_username': u'', u'nova_computes': [{u'datastore_regex': u'', u'vsphere_cluster': u'', u'service_name': u''}],
        #                              u'vcenter_host': u'', u'cinder': {u'enable': True}, u'az_name': u'vcenter', u'vcenter_password': u''}],
        #     u'network': {u'esxi_vlan_interface': u''}
        # }, u'metadata': [{u'fields': [{u'regex': {u'source': u'^(?!nova$)\\w+$', u'error': u'Invalid Availability zone name'}, u'type': u'text', u'description': u'Availability zone name', u'name': u'az_name', u'label': u'Availability zone'}, {u'regex': {u'source': u'^[a-zA-Z\\d]+[-\\.\\da-zA-Z]*$', u'error': u'Invalid vCenter host'}, u'type': u'text', u'description': u'vCenter host or IP', u'name': u'vcenter_host', u'label': u'vCenter host'}, {u'regex': {u'source': u'\\S', u'error': u'Empty vCenter username'}, u'type': u'text', u'description': u'vCenter username', u'name': u'vcenter_username', u'label': u'vCenter username'}, {u'regex': {u'source': u'\\S', u'error': u'Empty vCenter password'}, u'type': u'password', u'description': u'vCenter password', u'name': u'vcenter_password', u'label': u'vCenter password'}, {u'fields': [{u'regex': {u'source': u'\\S', u'error': u'Invalid VSphere cluster'}, u'type': u'text', u'description': u'VSphere cluster', u'name': u'vsphere_cluster', u'label': u'VSphere cluster'}, {u'regex': {u'source': u'^\\w+$', u'error': u'Invalid service name'}, u'type': u'text', u'description': u'Service name', u'name': u'service_name', u'label': u'Service name'}, {u'regex': {u'source': u'\\S', u'error': u'Invalid datastore regex'}, u'type': u'text', u'description': u'Datastore regex', u'name': u'datastore_regex', u'label': u'Datastore regex'}], u'type': u'array', u'name': u'nova_computes'}, {u'fields': [{u'type': u'checkbox', u'description': u'', u'name': u'enable', u'label': u'Enable Cinder'}], u'type': u'object', u'name': u'cinder'}], u'type': u'array', u'name': u'availability_zones'}, {u'restrictions': [{u'action': u'hide', u'condition': u"cluster:net_provider != 'nova_network' or networking_parameters:net_manager != 'VlanManager'"}], u'type': u'object', u'name': u'network', u'fields': [{u'regex': {u'source': u'\\S', u'error': u'Invalid Network Interface'}, u'type': u'text', u'description': u'VLAN interface', u'name': u'esxi_vlan_interface', u'label': u'VLAN interface'}]}, {u'restrictions': [{u'message': u'VMware vCenter datastore for images is not enabled in Settings tab', u'condition': u'settings:storage.images_vcenter.value == false or settings:common.use_vcenter == false'}], u'type': u'object', u'name': u'glance', u'fields': [{u'regex': {u'source': u'^[a-zA-Z\\d]+[-\\.\\da-zA-Z]*$', u'error': u'Invalid vCenter host'}, u'type': u'text', u'description': u'vCenter host or IP', u'name': u'vcenter_host', u'label': u'vCenter host'}, {u'regex': {u'source': u'\\S', u'error': u'Empty vCenter username'}, u'type': u'text', u'description': u'vCenter username', u'name': u'vcenter_username', u'label': u'vCenter username'}, {u'regex': {u'source': u'\\S', u'error': u'Empty vCenter password'}, u'type': u'password', u'description': u'vCenter password', u'name': u'vcenter_password', u'label': u'vCenter password'}, {u'regex': {u'source': u'\\S', u'error': u'Invalid Datacenter'}, u'type': u'text', u'description': u'Datacenter', u'name': u'datacenter', u'label': u'Datacenter'}, {u'regex': {u'source': u'\\S', u'error': u'Invalid Datastore'}, u'type': u'text', u'description': u'Datastore', u'name': u'datastore', u'label': u'Datastore'}]}
        #                  ]
        #  }


        # attrs
        # {
        #     u'external_dns':
        #         {
        #             u'dns_list': {u'value': u'8.8.8.8, 8.8.4.4', u'type': u'text', u'description': u'List of upstream DNS servers, separated by comma', u'weight': 10, u'label': u'DNS list'},
        #             u'metadata': {u'weight': 90, u'label': u'Upstream DNS'}
        #         },
        #     u'additional_components': {
        #         u'ceilometer': {u'value': False, u'type': u'checkbox', u'description': u'If selected, Ceilometer component will be installed', u'weight': 40, u'label': u'Install Ceilometer'},
        #         u'mongo': {u'restrictions': [u'settings:additional_components.ceilometer.value == false'], u'description': u'If selected, You can use external Mongo DB as ceilometer backend', u'weight': 40, u'value': False, u'label': u'Use external Mongo DB', u'type': u'checkbox'},
        #         u'heat': {u'value': True, u'type': u'hidden', u'description': u'', u'weight': 30, u'label': u''},
        #         u'murano': {u'restrictions': [u"cluster:net_provider != 'neutron'"], u'description': u'If selected, Murano component will be installed', u'weight': 20, u'value': False, u'label': u'Install Murano', u'type': u'checkbox'},
        #         u'sahara': {u'value': False, u'type': u'checkbox', u'description': u'If selected, Sahara component will be installed', u'weight': 10, u'label': u'Install Sahara'},
        #         u'metadata': {u'weight': 20, u'label': u'Additional Components'}
        #     },
        #     u'repo_setup': {
        #         u'repos': {u'type': u'custom_repo_configuration', u'value': [{u'priority': 20, u'type': u'rpm', u'name': u'mos', u'uri': u'http://127.0.0.1:8080/88751291-5.1/centos/x86_64'}], u'extra_priority': 15},
        #         u'metadata': {u'restrictions': [{u'action': u'hide', u'condition': u'true'}], u'weight': 50, u'label': u'Repositories'}
        #     },
        #     u'external_mongo': {u'mongo_db_name': {u'regex': {u'source': u'^\\w+$', u'error': u'Invalid database name'}, u'description': u'Mongo database name', u'weight': 30, u'value': u'ceilometer', u'label': u'Database name', u'type': u'text'},
        #                         u'mongo_replset': {u'value': u'', u'type': u'text', u'description': u'Name for Mongo replication set', u'weight': 30, u'label': u'Replset'},
        #                         u'mongo_user': {u'regex': {u'source': u'^\\w+$', u'error': u'Empty username'}, u'description': u'Mongo database username', u'weight': 30, u'value': u'ceilometer', u'label': u'Username', u'type': u'text'},
        #                         u'hosts_ip': {u'regex': {u'source': u'^(((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?),)*((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$', u'error': u'Invalid hosts ip sequence'},
        #                                       u'description': u'IP Addresses of MongoDB. Use comma to split IPs', u'weight': 30, u'value': u'', u'label': u'MongoDB hosts IP', u'type': u'text'},
        #                         u'mongo_password': {u'regex': {u'source': u'^\\S*$', u'error': u'Password contains spaces'}, u'description': u'Mongo database password', u'weight': 30, u'value': u'ceilometer', u'label': u'Password', u'type': u'password'},
        #                         u'metadata': {u'restrictions': [{u'action': u'hide', u'condition': u'settings:additional_components.mongo.value == false'}], u'weight': 20, u'label': u'External MongoDB'}
        #                         },
        #     u'kernel_params': {u'kernel': {u'value': u'console=ttyS0,9600 console=tty0 biosdevname=0 crashkernel=none rootdelay=90 nomodeset', u'type': u'text', u'description': u'Default kernel parameters', u'weight': 45, u'label': u'Initial parameters'},
        #                        u'metadata': {u'weight': 40, u'label': u'Kernel parameters'}
        #                        },
        #     u'storage': {u'iser': {u'restrictions': [u"settings:storage.volumes_lvm.value != true or settings:common.libvirt_type.value != 'kvm'"], u'description': u'High performance block storage: Cinder volumes over iSER protocol (iSCSI over RDMA). This feature requires SR-IOV capabilities in the NIC, and will use a dedicated virtual function for the storage network.', u'weight': 11, u'value': False, u'label': u'iSER protocol for volumes (Cinder)', u'type': u'checkbox'},
        #                  u'volumes_ceph': {u'restrictions': [u'settings:storage.volumes_lvm.value == true'], u'description': u'Configures Cinder to store volumes in Ceph RBD images.', u'weight': 20, u'value': False, u'label': u'Ceph RBD for volumes (Cinder)', u'type': u'checkbox'},
        #                  u'objects_ceph': {u'restrictions': [u'settings:storage.images_ceph.value == false'], u'description': u'Configures RadosGW front end for Ceph RBD. This exposes S3 and Swift API Interfaces. If enabled, this option will prevent Swift from installing.', u'weight': 80, u'value': False, u'label': u'Ceph RadosGW for objects (Swift API)', u'type': u'checkbox'},
        #                  u'ephemeral_ceph': {u'value': False, u'type': u'checkbox', u'description': u'Configures Nova to store ephemeral volumes in RBD. This works best if Ceph is enabled for volumes and images, too. Enables live migration of all types of Ceph backed VMs (without this option, live migration will only work with VMs launched from Cinder volumes).', u'weight': 75, u'label': u'Ceph RBD for ephemeral volumes (Nova)'},
        #                  u'volumes_lvm': {u'restrictions': [u'settings:storage.volumes_ceph.value == true'], u'description': u'It is recommended to have at least one Storage - Cinder LVM node.', u'weight': 10, u'value': True, u'label': u'Cinder LVM over iSCSI for volumes', u'type': u'checkbox'},
        #                  u'images_vcenter': {u'restrictions': [{u'action': u'hide', u'condition': u'settings:common.use_vcenter.value != true'}, {u'message': u'Only one Glance backend could be selected.', u'condition': u'settings:storage.images_ceph.value == true'}], u'description': u'Configures Glance to use the vCenter/ESXi backend to store images. If enabled, this option will prevent Swift from installing.', u'weight': 35, u'value': False, u'label': u'VMWare vCenter/ESXi datastore for images (Glance)', u'type': u'checkbox'},
        #                  u'osd_pool_size': {u'regex': {u'source': u'^[1-9]\\d*$', u'error': u'Invalid number'}, u'description': u"Configures the default number of object replicas in Ceph. This number must be equal to or lower than the number of deployed 'Storage - Ceph OSD' nodes.", u'weight': 85, u'value': u'2', u'label': u'Ceph object replication factor', u'type': u'text'},
        #                  u'images_ceph': {u'restrictions': [{u'settings:storage.images_vcenter.value == true': u'Only one Glance backend could be selected.'}], u'description': u'Configures Glance to use the Ceph RBD backend to store images. If enabled, this option will prevent Swift from installing.', u'weight': 30, u'value': False, u'label': u'Ceph RBD for images (Glance)', u'type': u'checkbox'}, u'metadata': {u'weight': 60, u'label': u'Storage'}
        #                  },
        #     u'access': {u'metadata': {u'weight': 10, u'label': u'Access'}, u'password': {u'regex': {u'source': u'\\S', u'error': u'Empty password'}, u'description': u'Password for Administrator', u'weight': 20, u'value': u'admin', u'label': u'password', u'type': u'password'},
        #                 u'email': {u'regex': {u'source': u'^\\S+@\\S+$', u'error': u'Invalid email'}, u'description': u'Email address for Administrator', u'weight': 40, u'value': u'admin@localhost', u'label': u'email', u'type': u'text'},
        #                 u'tenant': {u'regex': {u'source': u'^(?!services$)(?!nova$)(?!glance$)(?!keystone$)(?!neutron$)(?!cinder$)(?!swift$)(?!ceph$)(?![Gg]uest$)(?!.* +.*$).+', u'error': u'Invalid tenant name'}, u'description': u'Tenant (project) name for Administrator', u'weight': 30, u'value': u'admin', u'label': u'tenant', u'type': u'text'},
        #                 u'user': {u'regex': {u'source': u'^(?!services$)(?!nova$)(?!glance$)(?!keystone$)(?!neutron$)(?!cinder$)(?!swift$)(?!ceph$)(?![Gg]uest$)(?!.* +.*$).+', u'error': u'Invalid username'}, u'description': u'Username for Administrator', u'weight': 10, u'value': u'admin', u'label': u'username', u'type': u'text'}
        #                 },
        #     u'syslog': {u'syslog_port': {u'regex': {u'source': u'^([1-9][0-9]{0,3}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5])$', u'error': u'Invalid Syslog port'},
        #                                  u'description': u'Remote syslog port', u'weight': 20, u'value': u'514', u'label': u'Port', u'type': u'text'},
        #                 u'syslog_transport': {u'values': [{u'data': u'udp', u'description': u'', u'label': u'UDP'}, {u'data': u'tcp', u'description': u'', u'label': u'TCP'}], u'type': u'radio', u'value': u'tcp', u'weight': 30, u'label': u'Syslog transport protocol'},
        #                 u'syslog_server': {u'value': u'', u'type': u'text', u'description': u'Remote syslog hostname', u'weight': 10, u'label': u'Hostname'}, u'metadata': {u'weight': 50, u'label': u'Syslog'}},
        #     u'zabbix': {u'username': {u'value': u'admin', u'type': u'text', u'description': u'Username for Zabbix Administrator', u'weight': 10, u'label': u'username'},
        #                 u'password': {u'value': u'zabbix', u'type': u'password', u'description': u'Password for Zabbix Administrator', u'weight': 20, u'label': u'password'}, u'metadata': {u'restrictions': [{u'action': u'hide', u'condition': u"not ('experimental' in version:feature_groups)"}], u'weight': 70, u'label': u'Zabbix Access'}
        #                 },
        #     u'common': {u'use_vcenter': {u'type': u'hidden', u'value': False, u'weight': 30}, u'auto_assign_floating_ip': {u'restrictions': [u"cluster:net_provider == 'neutron'"], u'description': u'If selected, OpenStack will automatically assign a floating IP to a new instance', u'weight': 40, u'value': False, u'label': u'Auto assign floating IP', u'type': u'checkbox'},
        #                 u'use_cow_images': {u'value': True, u'type': u'checkbox', u'description': u"For most cases you will want qcow format. If it's disabled, raw image format will be used to run VMs. OpenStack with raw format currently does not support snapshotting.", u'weight': 50, u'label': u'Use qcow format for images'},
        #                 u'auth_key': {u'value': u'', u'type': u'textarea', u'description': u'Public key(s) to include in authorized_keys on deployed nodes', u'weight': 70, u'label': u'Public Key'},
        #                 u'libvirt_type': {u'values': [{u'data': u'kvm', u'description': u'Choose this type of hypervisor if you run OpenStack on hardware', u'label': u'KVM'}, {u'data': u'qemu', u'description': u'Choose this type of hypervisor if you run OpenStack on virtual hosts.', u'label': u'QEMU'}], u'type': u'radio', u'value': u'qemu', u'weight': 30, u'label': u'Hypervisor type'},
        #                 u'resume_guests_state_on_host_boot': {u'value': True, u'type': u'checkbox', u'description': u'Whether to resume previous guests state when the host reboots. If enabled, this option causes guests assigned to the host to resume their previous state. If the guest was running a restart will be attempted when nova-compute starts. If the guest was not running previously, a restart will not be attempted.', u'weight': 60, u'label': u'Resume guests state on host boot'},
        #                 u'debug': {u'value': False, u'type': u'checkbox', u'description': u'Debug logging mode provides more information, but requires more disk space.', u'weight': 20, u'label': u'OpenStack debug logging'},
        #                 u'nova_quota': {u'value': False, u'type': u'checkbox', u'description': u'Quotas are used to limit CPU and memory usage for tenants. Enabling quotas will increase load on the Nova database.', u'weight': 25, u'label': u'Nova quotas'}, u'metadata': {u'weight': 30, u'label': u'Common'}
        #                 },
        #     u'neutron_mellanox': {u'vf_num': {u'restrictions': [u"settings:neutron_mellanox.plugin.value != 'ethernet'"], u'description': u'Note that one virtual function will be reserved to the storage network, in case of choosing iSER.', u'weight': 70, u'value': u'16', u'label': u'Number of virtual NICs', u'type': u'text'}, u'metadata': {u'enabled': True, u'toggleable': False, u'weight': 50, u'label': u'Mellanox Neutron components'},
        #                           u'plugin': {u'type': u'radio', u'values': [{u'restrictions': [u'settings:storage.iser.value == true'], u'data': u'disabled', u'description': u'If selected, Mellanox drivers, Neutron and Cinder plugin will not be installed.', u'label': u'Mellanox drivers and plugins disabled'}, {u'restrictions': [u"settings:common.libvirt_type.value != 'kvm'"], u'data': u'drivers_only', u'description': u'If selected, Mellanox Ethernet drivers will be installed to support networking over Mellanox NIC. Mellanox Neutron plugin will not be installed.', u'label': u'Install only Mellanox drivers'},
        #                                                                      {u'restrictions': [u"settings:common.libvirt_type.value != 'kvm' or not (cluster:net_provider == 'neutron' and networking_parameters:segmentation_type == 'vlan')"], u'data': u'ethernet', u'description': u'If selected, both Mellanox Ethernet drivers and Mellanox network acceleration (Neutron) plugin will be installed.', u'label': u'Install Mellanox drivers and SR-IOV plugin'}], u'value': u'disabled', u'weight': 60, u'label': u'Mellanox drivers and SR-IOV plugin'}
        #                           },
        #     u'public_network_assignment': {u'assign_to_all_nodes': {u'value': False, u'type': u'checkbox', u'description': u'When disabled, public network will be assigned to controllers and zabbix-server only', u'weight': 10, u'label': u'Assign public network to all nodes'}, u'metadata': {u'restrictions': [{u'action': u'hide', u'condition': u"cluster:net_provider != 'neutron'"}], u'weight': 50, u'label': u'Public network assignment'}
        #                                    },
        #     u'workloads_collector': {
        #         u'username': {u'type': u'text', u'value': u'workloads_collector'},
        #         u'password': {u'type': u'password', u'value': u'B43VfH9h'},
        #         u'enabled': {u'type': u'hidden', u'value': True},
        #         u'tenant': {u'type': u'text', u'value': u'services'},
        #         u'metadata': {u'restrictions': [{u'action': u'hide', u'condition': u'true'}], u'weight': 10, u'label': u'Workloads Collector User'}
        #     },
        #     u'external_ntp': {
        #         u'ntp_list': {u'value': u'0.pool.ntp.org, 1.pool.ntp.org', u'type': u'text', u'description': u'List of upstream NTP servers, separated by comma', u'weight': 10, u'label': u'NTP servers list'},
        #         u'metadata': {u'weight': 100, u'label': u'Upstream NTP'}
        #     },
        #     u'provision': {u'method': {u'type': u'radio', u'values': [{u'data': u'image', u'description': u'Copying pre-built images on a disk.', u'label': u'Image'},
        #                                                               {u'data': u'cobbler', u'description': u'Install from scratch using anaconda or debian-installer.', u'label': u'Classic (use anaconda or debian-installer)'}], u'description': u'Which provision method to use for this cluster.', u'value': u'image', u'label': u'Provision method'}, u'metadata': {u'weight': 80, u'label': u'Provision'}},
        #     u'corosync': {u'group': {u'value': u'226.94.1.1', u'type': u'text', u'description': u'', u'weight': 10, u'label': u'Group'}, u'verified': {u'value': False, u'type': u'checkbox', u'description': u'Set True only if multicast is configured correctly on router.', u'weight': 10, u'label': u'Need to pass network verification.'}, u'port': {u'value': u'12000', u'type': u'text', u'description': u'', u'weight': 20, u'label': u'Port'}, u'metadata': {u'restrictions': [{u'action': u'hide', u'condition': u'true'}], u'weight': 50, u'label': u'Corosync'}
        #                   }
        # }
        return result


    def get_nodes_info(self, nodes):
        nodes_info = []
        for node in nodes:
            node_info = {
                'id': node.id,
                'group_id': node.group_id,
                'roles': node.roles,
                'os': node.os_platform,

                'status': node.status,
                'error_type': node.error_type,
                'online': node.online,

                'manufacturer': node.manufacturer,
                'platform_name': node.platform_name,

                'pending_addition': node.pending_addition,
                'pending_deletion': node.pending_deletion,
                'pending_roles': node.pending_roles,

                'nic_interfaces':
                self.get_node_intefaces_info(node.nic_interfaces, bond=False),
                'bond_interfaces':
                self.get_node_intefaces_info(node.bond_interfaces, bond=True),
            }
            nodes_info.append(node_info)
        return nodes_info

    def get_node_intefaces_info(self, interfaces, bond):
        ifs_info = []
        for interface in interfaces:
            if_info = {
                'id': interface.id
            }
            if bond:
                if_info['slaves'] = [s.id for s in interface.slaves]
            ifs_info.append(if_info)
        return ifs_info

    def get_node_groups_info(self, node_groups):
        groups_info = []
        for group in node_groups:
            group_info = {
                'id': group.id,
                'nodes': [n.id for n in group.nodes]
            }
            groups_info.append(group_info)
        return groups_info

    def get_installation_info(self):
        clusters_info = self.get_clusters_info()
        allocated_nodes_num = sum([c['nodes_num'] for c in clusters_info])
        unallocated_nodes_num = NodeCollection.filter_by(
            None, cluster_id=None).count()

        info = {
            'user_information': self.get_user_info(),
            'master_node_uid': self.get_master_node_uid(),
            'fuel_release': self.fuel_release_info(),
            'clusters': clusters_info,
            'clusters_num': len(clusters_info),
            'allocated_nodes_num': allocated_nodes_num,
            'unallocated_nodes_num': unallocated_nodes_num
        }

        return info

    def get_master_node_uid(self):
        return getattr(MasterNodeSettings.get_one(), 'master_node_uid', None)

    def get_user_info(self):
        try:
            stat_settings = MasterNodeSettings.get_one(). \
                settings.get("statistics", {})
            result = {
                "contact_info_provided":
                stat_settings.get("user_choice_saved", {}).get("value", False)
                and stat_settings.get("send_user_info", {}).get("value", False)
            }
            if result["contact_info_provided"]:
                result["name"] = stat_settings.get("name", {}).get("value")
                result["email"] = stat_settings.get("email", {}).get("value")
                result["company"] = stat_settings.get("company", {}).\
                    get("value")
            return result
        except AttributeError:
            return {"contact_info_provided": False}
