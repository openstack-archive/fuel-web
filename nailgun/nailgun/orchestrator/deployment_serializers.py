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
from itertools import groupby

import sqlalchemy as sa
from sqlalchemy.orm import joinedload

import math
import six

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy.models import Node
from nailgun.extensions import node_extension_call
from nailgun.extensions.volume_manager import manager as volume_manager
from nailgun import objects
from nailgun import utils

from nailgun.orchestrator.base_serializers import GraphBasedSerializer
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
    NeutronNetworkTemplateSerializer70
from nailgun.orchestrator.nova_serializers import \
    NovaNetworkDeploymentSerializer
from nailgun.orchestrator.nova_serializers import \
    NovaNetworkDeploymentSerializer61
from nailgun.orchestrator.nova_serializers import \
    NovaNetworkDeploymentSerializer70


class DeploymentMultinodeSerializer(GraphBasedSerializer):

    nova_network_serializer = NovaNetworkDeploymentSerializer
    neutron_network_serializer = NeutronNetworkDeploymentSerializer

    critical_roles = ['controller', 'ceph-osd', 'primary-mongo']

    def serialize(self, cluster, nodes, ignore_customized=False):
        """Method generates facts which
        through an orchestrator passes to puppet
        """
        def keyfunc(node):
            return bool(node.replaced_deployment_info)

        serialized_nodes = []
        for customized, node_group in groupby(nodes, keyfunc):
            if customized and not ignore_customized:
                serialized_nodes.extend(
                    self.serialize_customized(cluster, node_group))
            else:
                serialized_nodes.extend(self.serialize_generated(
                    cluster, node_group))

        # NOTE(dshulyak) tasks should not be preserved from replaced deployment
        # info, there is different mechanism to control changes in tasks
        # introduced during granular deployment, and that mech should be used
        self.set_tasks(serialized_nodes)
        return serialized_nodes

    def serialize_generated(self, cluster, nodes):
        nodes = self.serialize_nodes(nodes)
        common_attrs = self.get_common_attrs(cluster)

        self.set_deployment_priorities(nodes)
        self.set_critical_nodes(nodes)
        return [utils.dict_merge(node, common_attrs) for node in nodes]

    def serialize_customized(self, cluster, nodes):
        serialized = []
        for node in nodes:
            for role_data in node.replaced_deployment_info:
                serialized.append(role_data)
        return serialized

    def get_common_attrs(self, cluster):
        """Cluster attributes."""
        attrs = objects.Attributes.merged_attrs_values(cluster.attributes)
        release = self.current_release(cluster)

        attrs['deployment_mode'] = cluster.mode
        attrs['deployment_id'] = cluster.id
        attrs['openstack_version_prev'] = getattr(
            self.previous_release(cluster), 'version', None)
        attrs['openstack_version'] = release.version
        attrs['fuel_version'] = cluster.fuel_version
        attrs['nodes'] = self.node_list(
            objects.Cluster.get_nodes_not_for_deletion(cluster))

        # Adding params to workloads_collector
        if 'workloads_collector' not in attrs:
            attrs['workloads_collector'] = {}
        attrs['workloads_collector']['create_user'] = \
            objects.MasterNodeSettings.must_send_stats()
        username = attrs['workloads_collector'].pop('user', None)
        attrs['workloads_collector']['username'] = username

        for node in attrs['nodes']:
            if node['role'] in 'cinder':
                attrs['use_cinder'] = True

        self.set_storage_parameters(cluster, attrs)

        net_serializer = self.get_net_provider_serializer(cluster)
        net_common_attrs = net_serializer.get_common_attrs(cluster, attrs)
        attrs = utils.dict_merge(attrs, net_common_attrs)

        return attrs

    def current_release(self, cluster):
        """Actual cluster release."""
        return objects.Release.get_by_uid(cluster.pending_release_id) \
            if cluster.status == consts.CLUSTER_STATUSES.update \
            else cluster.release

    def previous_release(self, cluster):
        """Returns previous release.

        :param cluster: a ``Cluster`` instance to retrieve release from
        :returns: a ``Release`` instance of previous release or ``None``
            in case there's no previous release (fresh deployment).
        """
        if cluster.status == consts.CLUSTER_STATUSES.update:
            return cluster.release
        return None

    def set_storage_parameters(self, cluster, attrs):
        """Generate pg_num as the number of OSDs across the cluster
        multiplied by 100, divided by Ceph replication factor, and
        rounded up to the nearest power of 2.
        """
        osd_num = 0
        nodes = db().query(Node).filter(
            Node.cluster == cluster
        ).filter(sa.or_(
            Node.roles.any('ceph-osd'),
            Node.pending_roles.any('ceph-osd')
        )).options(joinedload('attributes'))

        for node in nodes:
            for disk in node_extension_call('get_node_volumes', node):
                for part in disk.get('volumes', []):
                    if part.get('name') == 'ceph' and part.get('size', 0) > 0:
                        osd_num += 1
        if osd_num > 0:
            repl = int(attrs['storage']['osd_pool_size'])
            pg_num = 2 ** int(math.ceil(math.log(osd_num * 100.0 / repl, 2)))
        else:
            pg_num = 128
        attrs['storage']['pg_num'] = pg_num

    @classmethod
    def node_list(cls, nodes):
        """Generate nodes list. Represents
        as "nodes" parameter in facts.
        """
        node_list = []

        for node in nodes:
            for role in objects.Node.all_roles(node):
                node_list.append(cls.serialize_node_for_node_list(node, role))

        return node_list

    @classmethod
    def serialize_node_for_node_list(cls, node, role):
        return {
            'uid': node.uid,
            'fqdn': node.fqdn,
            'name': objects.Node.get_slave_name(node),
            'role': role}

    # TODO(apopovych): we have more generical method 'filter_by_roles'
    def by_role(self, nodes, role):
        return filter(lambda node: node['role'] == role, nodes)

    def not_roles(self, nodes, roles):
        return filter(lambda node: node['role'] not in roles, nodes)

    def set_critical_nodes(self, nodes):
        """Set behavior on nodes deployment error
        during deployment process.
        """
        for n in nodes:
            n['fail_if_error'] = n['role'] in self.critical_roles

    def serialize_nodes(self, nodes):
        """Serialize node for each role.
        For example if node has two roles then
        in orchestrator will be passed two serialized
        nodes.
        """
        serialized_nodes = []
        for node in nodes:
            for role in objects.Node.all_roles(node):
                serialized_nodes.append(self.serialize_node(node, role))
        return serialized_nodes

    def serialize_node(self, node, role):
        """Serialize node, then it will be
        merged with common attributes
        """
        node_attrs = {
            # Yes, uid is really should be a string
            'uid': node.uid,
            'fqdn': node.fqdn,
            'status': node.status,
            'role': role,
            'vms_conf': node.attributes.vms_conf,
            # TODO (eli): need to remove, requried
            # for the fake thread only
            'online': node.online
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
                node_extension_call('get_node_volumes', node))
        return {'glance': {'image_cache_max_size': image_cache_max_size}}

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
        }
        # Generate a right path to image.
        c_attrs = node.cluster.attributes
        if 'ubuntu' in c_attrs['generated']['cobbler']['profile']:
            img_dir = '/usr/share/cirros-testvm/'
        else:
            img_dir = '/opt/vm/'
        image_data['img_path'] = '{0}cirros-x86_64-disk.img'.format(img_dir)

        glance_properties = []

        # Alternate VMWare specific values.
        if c_attrs['editable']['common']['libvirt_type']['value'] == 'vcenter':
            image_data.update({
                'disk_format': 'vmdk',
                'img_path': '{0}cirros-i386-disk.vmdk'.format(img_dir),
            })
            glance_properties.append('--property vmware_disktype=sparse')
            glance_properties.append('--property vmware_adaptertype=lsilogic')
            glance_properties.append('--property hypervisor_type=vmware')

        image_data['glance_properties'] = ' '.join(glance_properties)

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


class DeploymentHASerializer(DeploymentMultinodeSerializer):
    """Serializer for HA mode."""

    critical_roles = ['primary-controller',
                      'primary-mongo',
                      'primary-swift-proxy',
                      'ceph-osd',
                      'controller']

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
        """Node list
        """
        node_list = super(
            DeploymentHASerializer,
            cls
        ).node_list(nodes)

        for node in node_list:
            node['swift_zone'] = node['uid']

        return node_list

    def get_common_attrs(self, cluster):
        """Common attributes for all facts
        """
        common_attrs = super(
            DeploymentHASerializer,
            self
        ).get_common_attrs(cluster)

        net_manager = objects.Cluster.get_network_manager(cluster)

        common_attrs.update(net_manager.assign_vips_for_net_groups(cluster))

        common_attrs['mp'] = [
            {'point': '1', 'weight': '1'},
            {'point': '2', 'weight': '2'}]

        last_controller = self.get_last_controller(common_attrs['nodes'])
        common_attrs.update(last_controller)

        return common_attrs


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
        serialized_node = super(
            DeploymentMultinodeSerializer61, self).serialize_node(node, role)
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
        serialized_node = super(
            DeploymentHASerializer61, self).serialize_node(node, role)
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
            image_vmdk_data['glance_properties'] = ' '.join([
                '--property vmware_disktype=sparse',
                '--property vmware_adaptertype=lsilogic',
                '--property hypervisor_type=vmware'])
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

    def serialize_node(self, node, role):
        serialized_node = super(
            DeploymentHASerializer70, self).serialize_node(node, role)
        serialized_node['labels'] = node.labels

        return serialized_node


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
        }
    }

    env_mode = 'ha' if cluster.is_ha_mode else 'multinode'
    for version, serializers in six.iteritems(serializers_map):
        if cluster.release.environment_version.startswith(version):
            return serializers[env_mode]

    # return latest serializer by default
    latest_version = sorted(six.iterkeys(serializers_map))[-1]
    return serializers_map[latest_version][env_mode]


def serialize(orchestrator_graph, cluster, nodes, ignore_customized=False):
    """Serialization depends on deployment mode
    """
    objects.Cluster.set_primary_roles(cluster, nodes)
    env_version = cluster.release.environment_version

    # Only assign IPs for private (GRE) network in 6.1+
    if any([env_version.startswith(v) for v in ['5.0', '5.1', '6.0']]):
        objects.NodeCollection.prepare_for_lt_6_1_deployment(cluster.nodes)
    else:
        nst = cluster.network_config.get('segmentation_type')
        objects.NodeCollection.prepare_for_deployment(cluster.nodes, nst)

    serializer = get_serializer_for_cluster(cluster)(orchestrator_graph)

    return serializer.serialize(
        cluster, nodes, ignore_customized=ignore_customized)
