# -*- coding: utf-8 -*-

#    Copyright 2013 Mirantis, Inc.
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

"""Deployment serializers for orchestrator"""

from copy import deepcopy

import six

from nailgun import consts
from nailgun.db import db
from nailgun import extensions
from nailgun.extensions.volume_manager import manager as volume_manager
from nailgun.logger import logger
from nailgun import objects
from nailgun import plugins
from nailgun.settings import settings
from nailgun import utils
from nailgun.utils.ceph import get_pool_pg_count
from nailgun.utils.resolvers import NameMatchingPolicy
from nailgun.utils.resolvers import TagResolver

from nailgun.orchestrator.base_serializers import MuranoMetadataSerializerMixin
from nailgun.orchestrator.base_serializers import \
    VmwareDeploymentSerializerMixin
from nailgun.orchestrator.neutron_serializers import \
    NeutronNetworkDeploymentSerializer
from nailgun.orchestrator.neutron_serializers import \
    NeutronNetworkDeploymentSerializer51
from nailgun.orchestrator.neutron_serializers import \
    NeutronNetworkDeploymentSerializer60
from nailgun.orchestrator.neutron_serializers import \
    NeutronNetworkDeploymentSerializer61
from nailgun.orchestrator.neutron_serializers import \
    NeutronNetworkDeploymentSerializer70
from nailgun.orchestrator.neutron_serializers import \
    NeutronNetworkDeploymentSerializer80
from nailgun.orchestrator.neutron_serializers import \
    NeutronNetworkDeploymentSerializer90
from nailgun.orchestrator.neutron_serializers import \
    NeutronNetworkTemplateSerializer70
from nailgun.orchestrator.neutron_serializers import \
    NeutronNetworkTemplateSerializer80
from nailgun.orchestrator.neutron_serializers import \
    NeutronNetworkTemplateSerializer90
from nailgun.orchestrator.nova_serializers import \
    NovaNetworkDeploymentSerializer
from nailgun.orchestrator.nova_serializers import \
    NovaNetworkDeploymentSerializer61
from nailgun.orchestrator.nova_serializers import \
    NovaNetworkDeploymentSerializer70
from nailgun.orchestrator.provisioning_serializers import \
    ProvisionLCMSerializer


class DeploymentMultinodeSerializer(object):
    nova_network_serializer = NovaNetworkDeploymentSerializer
    neutron_network_serializer = NeutronNetworkDeploymentSerializer

    critical_roles = frozenset(('controller', 'ceph-osd', 'primary-mongo'))

    def __init__(self, tasks_graph=None):
        self.task_graph = tasks_graph
        self.all_nodes = None
        self.resolver = None
        self.initialized = None

    def initialize(self, cluster):
        self.all_nodes = objects.Cluster.get_nodes_not_for_deletion(cluster)
        self.resolver = TagResolver(self.all_nodes)
        self.initialized = cluster.id

    def finalize(self):
        self.all_nodes = None
        self.resolver = None
        self.initialized = None

    def _ensure_initialized_for(self, cluster):
        # TODO(bgaifullin) need to move initialize into __init__
        if self.initialized != cluster.id:
            self.initialize(cluster)

    def serialize(self, cluster, nodes,
                  ignore_customized=False, skip_extensions=False):
        """Method generates facts which are passed to puppet."""
        try:
            self.initialize(cluster)
            common_attrs = self.get_common_attrs(cluster)
            if not ignore_customized and cluster.replaced_deployment_info:
                # patch common attributes with custom deployment info
                utils.dict_update(
                    common_attrs, cluster.replaced_deployment_info
                )

            if not skip_extensions:
                extensions.\
                    fire_callback_on_cluster_serialization_for_deployment(
                        cluster, common_attrs
                    )

            serialized_nodes = []

            origin_nodes = []
            customized_nodes = []
            if ignore_customized:
                origin_nodes = nodes
            else:
                for node in nodes:
                    if node.replaced_deployment_info:
                        customized_nodes.append(node)
                    else:
                        origin_nodes.append(node)

            serialized_nodes.extend(
                self.serialize_generated(origin_nodes, skip_extensions)
            )
            serialized_nodes.extend(
                self.serialize_customized(customized_nodes)
            )

            # NOTE(dshulyak) tasks should not be preserved from replaced
            #  deployment info, there is different mechanism to control
            #  changes in tasks introduced during granular deployment,
            #  and that mech should be used
            self.set_tasks(serialized_nodes)

            deployment_info = {'common': common_attrs,
                               'nodes': serialized_nodes}
        finally:
            self.finalize()

        return deployment_info

    def serialize_generated(self, nodes, skip_extensions):
        serialized_nodes = self.serialize_nodes(nodes)
        nodes_map = {n.uid: n for n in nodes}

        self.set_deployment_priorities(serialized_nodes)
        for node_data in serialized_nodes:
            # the serialized nodes may contain fake nodes like master node
            # which does not have related db object. it shall be excluded.
            if not skip_extensions and node_data['uid'] in nodes_map:
                extensions.fire_callback_on_node_serialization_for_deployment(
                    nodes_map[node_data['uid']], node_data
                )
            yield node_data

    def serialize_customized(self, nodes):
        for node in nodes:
            for role_data in node.replaced_deployment_info:
                yield role_data

    def get_common_attrs(self, cluster):
        """Cluster attributes."""

        # tests call this method directly.
        # and we need this workaround to avoid refactoring a lot of tests.
        self._ensure_initialized_for(cluster)
        attrs = objects.Cluster.get_attributes(cluster)
        attrs = objects.Attributes.merged_attrs_values(attrs)

        attrs['deployment_mode'] = cluster.mode
        attrs['deployment_id'] = cluster.id
        attrs['openstack_version'] = cluster.release.version
        attrs['fuel_version'] = cluster.fuel_version
        attrs['nodes'] = self.node_list(self.all_nodes)

        # Adding params to workloads_collector
        if 'workloads_collector' not in attrs:
            attrs['workloads_collector'] = {}
        attrs['workloads_collector']['create_user'] = \
            objects.MasterNodeSettings.must_send_stats()
        username = attrs['workloads_collector'].pop('user', None)
        attrs['workloads_collector']['username'] = username

        if self.resolver.resolve(['cinder']):
            attrs['use_cinder'] = True

        self.set_storage_parameters(cluster, attrs)

        net_serializer = self.get_net_provider_serializer(cluster)
        net_common_attrs = net_serializer.get_common_attrs(cluster, attrs)
        utils.dict_update(attrs, net_common_attrs)
        self.inject_list_of_plugins(attrs, cluster)

        return attrs

    def set_storage_parameters(self, cluster, attrs):
        """Generate pg_num

        pg_num is generated as the number of OSDs across the cluster
        multiplied by 100, divided by Ceph replication factor, and
        rounded up to the nearest power of 2.
        """
        osd_num = 0
        ceph_nodes_uids = self.resolver.resolve(['ceph-osd'])
        ceph_nodes = objects.NodeCollection.filter_by_id_list(
            self.all_nodes, ceph_nodes_uids
        )
        call_node_extension = extensions.node_extension_call
        for node in ceph_nodes:
            for disk in call_node_extension('get_node_volumes', node):
                for part in disk.get('volumes', []):
                    if part.get('name') == 'ceph' and part.get('size', 0) > 0:
                        osd_num += 1

        storage_attrs = attrs['storage']

        pg_counts = get_pool_pg_count(
            osd_num=osd_num,
            pool_sz=int(storage_attrs['osd_pool_size']),
            ceph_version='firefly',
            volumes_ceph=storage_attrs['volumes_ceph'],
            objects_ceph=storage_attrs['objects_ceph'],
            ephemeral_ceph=storage_attrs['ephemeral_ceph'],
            images_ceph=storage_attrs['images_ceph'],
            emulate_pre_7_0=False)

        # Log {pool_name: pg_count} mapping
        pg_str = ", ".join(map("{0[0]}={0[1]}".format, pg_counts.items()))
        logger.debug("Ceph: PG values {%s}", pg_str)

        storage_attrs['pg_num'] = pg_counts['default_pg_num']
        storage_attrs['per_pool_pg_nums'] = pg_counts

    @classmethod
    def node_list(cls, nodes):
        """Generate nodes list. Represents as "nodes" parameter in facts."""
        node_list = []

        for node in nodes:
            for role in objects.Node.all_tags(node):
                node_list.append(cls.serialize_node_for_node_list(node, role))

        return node_list

    @classmethod
    def serialize_node_for_node_list(cls, node, role):
        return {
            'uid': node.uid,
            'fqdn': objects.Node.get_node_fqdn(node),
            'name': objects.Node.get_slave_name(node),
            'role': role}

    # TODO(apopovych): we have more generical method 'filter_by_roles'
    def by_role(self, nodes, role):
        return filter(lambda node: node['role'] == role, nodes)

    def not_roles(self, nodes, roles):
        return filter(lambda node: node['role'] not in roles, nodes)

    def serialize_nodes(self, nodes):
        """Serialize node for each role.

        For example if node has two roles then
        in orchestrator will be passed two serialized
        nodes.
        """
        serialized_nodes = []
        for node in nodes:
            for role in objects.Node.all_tags(node):
                serialized_nodes.append(
                    self.serialize_node(node, role)
                )
        return serialized_nodes

    def serialize_node(self, node, role):
        """Serialize node, then it will be merged with common attributes."""
        node_attrs = {
            # Yes, uid is really should be a string
            'uid': node.uid,
            'fqdn': objects.Node.get_node_fqdn(node),
            'status': node.status,
            'role': role,
            'vms_conf': node.vms_conf,
            'fail_if_error': role in self.critical_roles,
            # TODO(eli): need to remove, requried for the fake thread only
            'online': node.online,
        }

        net_serializer = self.get_net_provider_serializer(node.cluster)
        node_attrs.update(net_serializer.get_node_attrs(node))
        node_attrs.update(net_serializer.network_ranges(node.group_id))
        node_attrs.update(self.get_image_cache_max_size(node))
        node_attrs.update(self.generate_test_vm_image_data(node))

        return node_attrs

    def get_image_cache_max_size(self, node):
        images_ceph = (node.cluster.attributes['editable']['storage']
                       ['images_ceph']['value'])
        if images_ceph:
            image_cache_max_size = '0'
        else:
            image_cache_max_size = volume_manager.calc_glance_cache_size(
                extensions.node_extension_call('get_node_volumes', node))
        return {'glance': {'image_cache_max_size': image_cache_max_size}}

    def generate_properties_arguments(self, properties_data):
        """build a string of properties from a key value hash"""
        properties = []
        for key, value in six.iteritems(properties_data):
            properties.append('--property {key}={value}'.format(
                key=key, value=value))
        return ' '.join(properties)

    def generate_test_vm_image_data(self, node):
        # Instantiate all default values in dict.
        image_data = {
            'container_format': 'bare',
            'public': 'true',
            'disk_format': 'qcow2',
            'img_name': 'TestVM',
            'img_path': '',
            'os_name': 'cirros',
            'min_ram': 64,
            'glance_properties': '',
            'properties': {},
        }
        # Generate a right path to image.
        c_attrs = node.cluster.attributes
        if 'ubuntu' in c_attrs['generated']['cobbler']['profile']:
            img_dir = '/usr/share/cirros-testvm/'
        else:
            img_dir = '/opt/vm/'
        image_data['img_path'] = '{0}cirros-x86_64-disk.img'.format(img_dir)

        properties_data = {}

        # Alternate VMWare specific values.
        if c_attrs['editable']['common']['libvirt_type']['value'] == 'vcenter':
            image_data.update({
                'disk_format': 'vmdk',
                'img_path': '{0}cirros-i386-disk.vmdk'.format(img_dir),
            })
            properties_data = {
                'vmware_disktype': 'sparse',
                'vmware_adaptertype': 'lsiLogic',
                'hypervisor_type': 'vmware'
            }

        # NOTE(aschultz): properties was added as part of N and should be
        # used infavor of glance_properties
        image_data['glance_properties'] = self.generate_properties_arguments(
            properties_data)
        image_data['properties'] = properties_data

        return {'test_vm_image': image_data}

    @classmethod
    def get_net_provider_serializer(cls, cluster):
        if cluster.net_provider == 'nova_network':
            return cls.nova_network_serializer
        else:
            return cls.neutron_network_serializer

    def filter_by_roles(self, nodes, roles):
        return filter(
            lambda node: node['role'] in roles, nodes)

    def set_deployment_priorities(self, nodes):
        if self.task_graph is not None:
            self.task_graph.add_priorities(nodes)

    def set_tasks(self, serialized_nodes):
        if self.task_graph is not None:
            for node in serialized_nodes:
                node['tasks'] = self.task_graph.deploy_task_serialize(node)

    def inject_list_of_plugins(self, attributes, cluster):
        """Added information about plugins to serialized attributes.

        :param attributes: the serialized attributes
        :param cluster: the cluster object
        """
        plugins = objects.ClusterPlugin.get_enabled(cluster.id)
        attributes['plugins'] = [
            self.serialize_plugin(cluster, p) for p in plugins
        ]

    @classmethod
    def serialize_plugin(cls, cluster, plugin):
        """Gets plugin information to include into serialized attributes.

        :param cluster: the cluster object
        :param plugin: the plugin object
        """
        return plugin['name']


class DeploymentHASerializer(DeploymentMultinodeSerializer):
    """Serializer for HA mode."""

    critical_roles = frozenset((
        'primary-controller',
        'primary-mongo',
        'primary-swift-proxy',
        'ceph-osd',
        'controller'
    ))

    def get_last_controller(self, nodes):
        sorted_nodes = sorted(
            nodes, key=lambda node: int(node['uid']))

        controller_nodes = self.filter_by_roles(
            sorted_nodes, ['controller', 'primary-controller'])

        last_controller = None
        if len(controller_nodes) > 0:
            last_controller = controller_nodes[-1]['name']

        return {'last_controller': last_controller}

    @classmethod
    def node_list(cls, nodes):
        """Node list."""
        node_list = super(
            DeploymentHASerializer,
            cls
        ).node_list(nodes)

        for node in node_list:
            node['swift_zone'] = node['uid']

        return node_list

    def get_common_attrs(self, cluster):
        """Common attributes for all facts."""
        common_attrs = super(
            DeploymentHASerializer,
            self
        ).get_common_attrs(cluster)

        common_attrs.update(self.get_assigned_vips(cluster))

        common_attrs['mp'] = [
            {'point': '1', 'weight': '1'},
            {'point': '2', 'weight': '2'}]

        last_controller = self.get_last_controller(common_attrs['nodes'])
        common_attrs.update(last_controller)

        return common_attrs

    def get_assigned_vips(self, cluster):
        """Assign and get vips for net groups."""
        return objects.Cluster.get_network_manager(cluster).\
            assign_vips_for_net_groups(cluster)


class DeploymentMultinodeSerializer50(MuranoMetadataSerializerMixin,
                                      DeploymentMultinodeSerializer):
    pass


class DeploymentHASerializer50(MuranoMetadataSerializerMixin,
                               DeploymentHASerializer):
    pass


class DeploymentMultinodeSerializer51(DeploymentMultinodeSerializer50):

    nova_network_serializer = NovaNetworkDeploymentSerializer
    neutron_network_serializer = NeutronNetworkDeploymentSerializer51


class DeploymentHASerializer51(DeploymentHASerializer50):

    nova_network_serializer = NovaNetworkDeploymentSerializer
    neutron_network_serializer = NeutronNetworkDeploymentSerializer51


class DeploymentMultinodeSerializer60(DeploymentMultinodeSerializer50):

    nova_network_serializer = NovaNetworkDeploymentSerializer
    neutron_network_serializer = NeutronNetworkDeploymentSerializer60


class DeploymentHASerializer60(DeploymentHASerializer50):

    nova_network_serializer = NovaNetworkDeploymentSerializer
    neutron_network_serializer = NeutronNetworkDeploymentSerializer60


class DeploymentMultinodeSerializer61(DeploymentMultinodeSerializer,
                                      VmwareDeploymentSerializerMixin):

    nova_network_serializer = NovaNetworkDeploymentSerializer61
    neutron_network_serializer = NeutronNetworkDeploymentSerializer61

    def serialize_node(self, node, role):
        base = super(DeploymentMultinodeSerializer61, self)
        serialized_node = base.serialize_node(node, role)
        serialized_node['user_node_name'] = node.name
        serialized_node.update(self.generate_vmware_data(node))

        return serialized_node

    @classmethod
    def serialize_node_for_node_list(cls, node, role):
        serialized_node = super(
            DeploymentMultinodeSerializer61,
            cls).serialize_node_for_node_list(node, role)
        serialized_node['user_node_name'] = node.name
        return serialized_node


class DeploymentHASerializer61(DeploymentHASerializer,
                               VmwareDeploymentSerializerMixin):

    nova_network_serializer = NovaNetworkDeploymentSerializer61
    neutron_network_serializer = NeutronNetworkDeploymentSerializer61

    def serialize_node(self, node, role):
        base = super(DeploymentHASerializer61, self)
        serialized_node = base.serialize_node(node, role)
        serialized_node['user_node_name'] = node.name
        serialized_node.update(self.generate_vmware_data(node))

        return serialized_node

    @classmethod
    def serialize_node_for_node_list(cls, node, role):
        serialized_node = super(
            DeploymentHASerializer61,
            cls).serialize_node_for_node_list(node, role)
        serialized_node['user_node_name'] = node.name
        return serialized_node

    # Alternate VMWare specific values.
    # FiXME(who): srogov
    # This a temporary workaround to keep existing functioanality
    # after fully implementation of the multi HV support and astute part
    # for multiple images support, it is need to change
    # dict image_data['test_vm_image'] to list of dicts
    def generate_test_vm_image_data(self, node):
        attrs = node.cluster.attributes
        image_data = super(
            DeploymentHASerializer61,
            self).generate_test_vm_image_data(node)

        images_data = {}
        images_data['test_vm_image'] = []
        if attrs.get('editable', {}).get('common', {}). \
           get('use_vcenter', {}).get('value') is True:
            image_vmdk_data = deepcopy(image_data['test_vm_image'])
            img_path = image_vmdk_data['img_path']. \
                replace('x86_64-disk.img', 'i386-disk.vmdk')
            image_vmdk_data.update({
                'img_name': 'TestVM-VMDK',
                'disk_format': 'vmdk',
                'img_path': img_path,
            })
            properties_data = {
                'vmware_disktype': 'sparse',
                'vmware_adaptertype': 'lsiLogic',
                'hypervisor_type': 'vmware'
            }
            glance_properties = self.generate_properties_arguments(
                properties_data)

            # NOTE(aschultz): properties was added as part of N and should be
            # used infavor of glance_properties
            image_vmdk_data['glance_properties'] = glance_properties
            image_vmdk_data['properties'] = properties_data
            images_data['test_vm_image'].append(image_vmdk_data)
            images_data['test_vm_image'].append(image_data['test_vm_image'])
        else:
            images_data = image_data

        return images_data


class DeploymentHASerializer70(DeploymentHASerializer61):
    # nova_network_serializer is just for compatibility with current BVTs
    # and other tests. It can be removed when tests are fixed.
    nova_network_serializer = NovaNetworkDeploymentSerializer70

    @classmethod
    def get_net_provider_serializer(cls, cluster):
        if cluster.net_provider == consts.CLUSTER_NET_PROVIDERS.nova_network:
            return cls.nova_network_serializer
        elif cluster.network_config.configuration_template:
            return NeutronNetworkTemplateSerializer70
        else:
            return NeutronNetworkDeploymentSerializer70

    def get_assigned_vips(self, cluster):
        return {}


class DeploymentHASerializer80(DeploymentHASerializer70):

    def serialize_node(self, node, role):
        base = super(DeploymentHASerializer80, self)
        serialized_node = base.serialize_node(node, role)
        serialized_node.update(self.generate_node_volumes_data(node))

        return serialized_node

    @classmethod
    def get_net_provider_serializer(cls, cluster):
        if cluster.network_config.configuration_template:
            return NeutronNetworkTemplateSerializer80
        else:
            return NeutronNetworkDeploymentSerializer80

    def generate_node_volumes_data(self, node):
        """Serialize information about disks.

        This function returns information about disks and
        volume groups for each node in cluster.
        Will be passed to Astute.
        """
        volumes = extensions.node_extension_call('get_node_volumes', node)
        return {'node_volumes': volumes}


class DeploymentHASerializer90(DeploymentHASerializer80):

    def inject_murano_settings(self, data):
        return data

    def get_common_attrs(self, cluster):
        attrs = super(DeploymentHASerializer90, self).get_common_attrs(cluster)

        for node in objects.Cluster.get_nodes_not_for_deletion(cluster):
            name = objects.Node.permanent_id(node)
            node_attrs = attrs['network_metadata']['nodes'][name]

            node_attrs['nova_cpu_pinning_enabled'] = \
                objects.NodeAttributes.is_nova_cpu_pinning_enabled(node)
            node_attrs['nova_hugepages_enabled'] = (
                objects.NodeAttributes.is_nova_hugepages_enabled(node))

        return attrs

    @classmethod
    def get_net_provider_serializer(cls, cluster):
        if cluster.network_config.configuration_template:
            return NeutronNetworkTemplateSerializer90
        else:
            return NeutronNetworkDeploymentSerializer90

    @classmethod
    def serialize_node_for_node_list(cls, node, role):
        serialized_node = super(
            DeploymentHASerializer90,
            cls).serialize_node_for_node_list(node, role)

        for section_name, section_attributes in six.iteritems(
                plugins.manager.PluginManager.
                get_plugin_node_attributes(node)):
            section_attributes.pop('metadata', None)
            serialized_node[section_name] = {
                k: v.get('value') for k, v in six.iteritems(section_attributes)
            }
        return serialized_node

    def serialize_node(self, node, role):
        base = super(DeploymentHASerializer90, self)
        serialized_node = base.serialize_node(node, role)
        self.serialize_node_attributes(node, serialized_node)
        return serialized_node

    def serialize_node_attributes(self, node, serialized_node):
        self.generate_cpu_pinning(node, serialized_node)
        self.generate_node_hugepages(node, serialized_node)

    def generate_cpu_pinning(self, node, serialized_node):
        if not objects.NodeAttributes.is_cpu_pinning_enabled(node):
            return

        pinning_info = objects.NodeAttributes.distribute_node_cpus(node)
        cpu_pinning = pinning_info['components']

        self._generate_nova_cpu_pinning(
            serialized_node,
            cpu_pinning.pop('nova', [])
        )
        self._generate_dpdk_cpu_pinning(
            serialized_node,
            cpu_pinning.pop('ovs_core_mask', []),
            cpu_pinning.pop('ovs_pmd_core_mask', [])
        )
        # Allow user to override CPU distribution using attributes
        if not serialized_node.get('dpdk'):
            serialized_node['dpdk'] = {}
        serialized_node['dpdk'].update(
            objects.Node.get_attributes(node).get('dpdk', {})
        )
        serialized_node['cpu_pinning'] = cpu_pinning

    def generate_node_hugepages(self, node, serialized_node):
        if not objects.NodeAttributes.is_hugepages_enabled(node):
            return
        self._generate_nova_hugepages(node, serialized_node)
        self._generate_dpdk_hugepages(node, serialized_node)
        self._generate_hugepages_distribution(node, serialized_node)

    @staticmethod
    def _generate_nova_cpu_pinning(serialized_node, cpus):
        if not cpus:
            return

        serialized_node.setdefault('nova', {})['cpu_pinning'] = cpus

    @staticmethod
    def _generate_dpdk_cpu_pinning(serialized_node, ovs_core_cpus,
                                   ovs_pmd_core_cpus):
        """Translate list of CPU ids to DPDK masks

        ovsdpdk application may use pinned CPUs
        it takes CPU masks. CPU mask contains information
        about pinned CPUs: N-th bit is set to 1 if
        appropriate CPU id is pinned for DPDK process
        """
        if not ovs_core_cpus and not ovs_pmd_core_cpus:
            return

        ovs_core_mask = 0
        ovs_pmd_core_mask = 0

        for cpu in ovs_core_cpus:
            ovs_core_mask |= (1 << cpu)

        for cpu in ovs_pmd_core_cpus:
            ovs_pmd_core_mask |= (1 << cpu)

        if not serialized_node.get('dpdk'):
            serialized_node['dpdk'] = {}
        serialized_node['dpdk'].update({
            'ovs_core_mask': hex(ovs_core_mask),
            'ovs_pmd_core_mask': hex(ovs_pmd_core_mask),
        })

    @staticmethod
    def _generate_nova_hugepages(node, serialized_node):
        serialized_node.setdefault('nova', {})['enable_hugepages'] = (
            objects.NodeAttributes.is_nova_hugepages_enabled(node))

    @staticmethod
    def _generate_dpdk_hugepages(node, serialized_node):
        serialized_node.setdefault('dpdk', {}).update(
            objects.NodeAttributes.dpdk_hugepages_attrs(node))

    @classmethod
    def _generate_hugepages_distribution(self, node, serialized_node):
        hugepages = objects.NodeAttributes.distribute_hugepages(node)

        # FIXME(asvechnikov): We should skip our distribution
        # due to LP bug #1560532, so we can't configure 1G hugepages
        # in runtime. This limitation should gone with kernel 3.16
        skip = any((x['size'] == 1024 ** 2) for x in hugepages)
        if hugepages and not skip:
            serialized_node.setdefault('hugepages', []).extend(
                hugepages)


class DeploymentLCMSerializer(DeploymentHASerializer90):
    _configs = None
    _cluster_info = None
    _provision_serializer = None
    _priorities = {
        consts.OPENSTACK_CONFIG_TYPES.cluster: 0,
        consts.OPENSTACK_CONFIG_TYPES.role: 1,
        consts.OPENSTACK_CONFIG_TYPES.node: 2,
    }

    def initialize(self, cluster):
        super(DeploymentLCMSerializer, self).initialize(cluster)
        self._configs = sorted(
            objects.OpenstackConfigCollection.filter_by(
                None, cluster_id=cluster.id
            ),
            key=lambda x: self._priorities[x.config_type]
        )
        self._provision_serializer = ProvisionLCMSerializer()

    def finalize(self):
        self._configs = None
        self._provision_serializer = None
        self._cluster_info = None
        super(DeploymentLCMSerializer, self).finalize()

    def get_common_attrs(self, cluster):
        attrs = super(DeploymentLCMSerializer, self).get_common_attrs(
            cluster
        )
        attrs['cluster'] = objects.Cluster.to_dict(
            cluster, fields=("id", "name", "fuel_version", "status", "mode")
        )
        attrs['release'] = objects.Release.to_dict(
            cluster.release, fields=('name', 'version', 'operating_system')
        )
        # the ReleaseSerializer adds this attribute certainly
        attrs['release'].pop('is_deployable', None)

        provision = attrs.setdefault('provision', {})
        utils.dict_update(
            provision,
            self._provision_serializer.serialize_cluster_info(cluster, attrs)
        )
        # TODO(bgaifullin) remove using cluster_info
        #  in serialize_node_for_provision
        self._cluster_info = attrs
        return attrs

    def serialize_customized(self, nodes):
        for node in nodes:
            data = {}
            roles = []
            for role_data in node.replaced_deployment_info:
                if 'role' in role_data:
                    # if replaced_deployment_info consists
                    # of old serialized info, the old info
                    # have serialized data per role
                    roles.append(role_data.pop('role'))
                utils.dict_update(data, role_data)
            if roles:
                data['roles'] = roles
            self.inject_provision_info(node, data)
            yield data

    def serialize_nodes(self, nodes):
        serialized_nodes = []
        for node in nodes:
            roles = objects.Node.all_tags(node)
            if roles:
                serialized_nodes.append(
                    self.serialize_node(node, roles)
                )
        # added master node
        serialized_nodes.append({
            'uid': consts.MASTER_NODE_UID,
            'roles': [consts.TASK_ROLES.master]
        })
        return serialized_nodes

    def serialize_node(self, node, roles):
        # serialize all roles to one config
        # Since there is no role depended things except
        # OpenStack configs, we can do this
        base = super(DeploymentLCMSerializer, self)
        serialized_node = base.serialize_node(node, roles[0])
        del serialized_node['role']
        serialized_node['roles'] = roles
        if node.pending_deletion:
            serialized_node['deleted'] = True
        self.inject_configs(node, serialized_node)
        self.inject_provision_info(node, serialized_node)
        return serialized_node

    @classmethod
    def serialize_plugin(cls, cluster, plugin):
        os_name = cluster.release.operating_system
        adapter = plugins.wrap_plugin(plugin)
        result = {
            'name': plugin['name'],
            'scripts': [
                {
                    'remote_url': adapter.master_scripts_path(cluster),
                    'local_path': adapter.slaves_scripts_path
                }
            ]
        }

        if not adapter.repo_files(cluster):
            return result

        # TODO(bgaifullin) move priority to plugin metadata
        if os_name == consts.RELEASE_OS.centos:
            repo = {
                'type': 'rpm',
                'name': adapter.path_name,
                'uri': adapter.repo_url(cluster),
                'priority': settings.REPO_PRIORITIES['plugins']['centos']
            }
        elif os_name == consts.RELEASE_OS.ubuntu:
            repo = {
                'type': 'deb',
                'name': adapter.path_name,
                'uri': adapter.repo_url(cluster),
                'suite': '/',
                'section': '',
                'priority': settings.REPO_PRIORITIES['plugins']['ubuntu']
            }
        else:
            logger.warning("Unsupported OS: %s.", os_name)
            return result

        result['repositories'] = [repo]
        return result

    def inject_configs(self, node, output):
        node_config = output.setdefault('configuration', {})
        for config in self._configs:
            if config.config_type == consts.OPENSTACK_CONFIG_TYPES.cluster:
                utils.dict_update(node_config, config.configuration, 1)
            elif config.config_type == consts.OPENSTACK_CONFIG_TYPES.role:
                # (asaprykin): objects.Node.all_roles() has a side effect,
                # it replaces "<rolename>" with "primary-<rolename>"
                # in case of primary role.
                for role in node.all_roles:
                    if NameMatchingPolicy.create(config.node_role).match(role):
                        utils.dict_update(node_config, config.configuration, 1)
            elif config.config_type == consts.OPENSTACK_CONFIG_TYPES.node:
                if config.node_id == node.id:
                    utils.dict_update(node_config, config.configuration, 1)

    def inject_provision_info(self, node, data):
        # TODO(bgaifullin) serialize_node_info should be reworked
        if not self._cluster_info:
            self._cluster_info = self.get_common_attrs(node.cluster)

        if node.replaced_provisioning_info:
            info = node.replaced_provisioning_info
        else:
            info = self._provision_serializer.serialize_node_info(
                self._cluster_info, node
            )
        utils.dict_update(data.setdefault('provision', {}), info)


def get_serializer_for_cluster(cluster):
    """Returns a serializer depends on a given `cluster`.

    :param cluster: cluster to process
    :returns: a serializer for a given cluster
    """
    serializers_map = {
        '5.0': {
            'multinode': DeploymentMultinodeSerializer50,
            'ha': DeploymentHASerializer50,
        },
        '5.1': {
            'multinode': DeploymentMultinodeSerializer51,
            'ha': DeploymentHASerializer51,
        },
        '6.0': {
            'multinode': DeploymentMultinodeSerializer60,
            'ha': DeploymentHASerializer60,
        },
        '6.1': {
            'multinode': DeploymentMultinodeSerializer61,
            'ha': DeploymentHASerializer61,
        },
        '7.0': {
            # Multinode is not supported anymore
            'ha': DeploymentHASerializer70,
        },
        '8.0': {
            'ha': DeploymentHASerializer80,
        },
        '9.0': {
            'ha': DeploymentHASerializer90,
        }
    }

    env_mode = 'ha' if cluster.is_ha_mode else 'multinode'
    for version, serializers in six.iteritems(serializers_map):
        if cluster.release.environment_version.startswith(version):
            return serializers[env_mode]

    # return latest serializer by default
    latest_version = sorted(six.iterkeys(serializers_map))[-1]
    return serializers_map[latest_version][env_mode]


def _invoke_serializer(serializer, cluster, nodes,
                       ignore_customized, skip_extensions):
    # TODO(apply only for specified subset of nodes)
    objects.Cluster.prepare_for_deployment(cluster, cluster.nodes)
    objects.Cluster.set_primary_tags(cluster, nodes)
    # commit the transaction immediately so that the updates
    # made to nodes don't lock other updates to these nodes
    # until this, possibly very long, transation ends.
    db().commit()
    return serializer.serialize(
        cluster, nodes,
        ignore_customized=ignore_customized, skip_extensions=skip_extensions
    )


def serialize(orchestrator_graph, cluster, nodes,
              ignore_customized=False, skip_extensions=False):
    """Serialization depends on deployment mode."""
    serialized = _invoke_serializer(
        get_serializer_for_cluster(cluster)(orchestrator_graph),
        cluster, nodes, ignore_customized, skip_extensions
    )
    return serialized


def serialize_for_lcm(cluster, nodes,
                      ignore_customized=False, skip_extensions=False):
    return _invoke_serializer(
        DeploymentLCMSerializer(), cluster, nodes,
        ignore_customized, skip_extensions
    )


def deployment_info_to_legacy(deployment_info):
    common_attrs = deployment_info['common']
    nodes = [utils.dict_merge(common_attrs, n)
             for n in deployment_info['nodes']]
    return nodes
