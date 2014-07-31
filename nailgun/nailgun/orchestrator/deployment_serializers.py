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
import math

from netaddr import IPNetwork
from sqlalchemy import and_
from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from nailgun import objects

from nailgun.plugins.hooks import rpc as rpc_hooks

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun.db.sqlalchemy.models import Node
from nailgun.errors import errors
from nailgun.logger import logger
from nailgun.objects import Cluster
from nailgun.settings import settings
from nailgun.utils import dict_merge
from nailgun.volumes import manager as volume_manager


class Priority(object):
    """Node with priority 0 will be deployed first.
    We have step equal 100 because we want to allow
    user redefine deployment order and he can use free space
    between prioriries.
    """

    def __init__(self):
        self.step = 100
        self.priority = 0

    @property
    def next(self):
        self.priority += self.step
        return self.priority

    @property
    def current(self):
        return self.priority


def get_nodes_not_for_deletion(cluster):
    """All clusters nodes except nodes for deletion."""
    return db().query(Node).filter(
        and_(Node.cluster == cluster,
             False == Node.pending_deletion)).order_by(Node.id)


class DeploymentMultinodeSerializer(object):

    critical_roles = ['controller', 'ceph-osd', 'primary-mongo']

    @classmethod
    def serialize(cls, cluster, nodes, ignore_customized=False):
        """Method generates facts which
        through an orchestrator passes to puppet
        """
        serialized_nodes = []
        keyfunc = lambda node: bool(node.replaced_deployment_info)
        for customized, node_group in groupby(nodes, keyfunc):
            if customized and not ignore_customized:
                serialized_nodes.extend(
                    cls.serialize_customized(cluster, node_group))
            else:
                serialized_nodes.extend(cls.serialize_generated(
                    cluster, node_group))
        return serialized_nodes

    @classmethod
    def serialize_generated(cls, cluster, nodes):
        nodes = cls.serialize_nodes(nodes)
        common_attrs = cls.get_common_attrs(cluster)

        cls.set_deployment_priorities(nodes)
        cls.set_critical_nodes(cluster, nodes)

        return [dict_merge(node, common_attrs) for node in nodes]

    @classmethod
    def serialize_customized(cls, cluster, nodes):
        serialized = []
        release_data = objects.Release.get_orchestrator_data_dict(
            cls.current_release(cluster))
        for node in nodes:
            for role_data in node.replaced_deployment_info:
                role_data.update(release_data)
                serialized.append(role_data)
        return serialized

    @classmethod
    def get_common_attrs(cls, cluster):
        """Cluster attributes."""
        attrs = objects.Attributes.merged_attrs_values(
            cluster.attributes
        )
        release = cls.current_release(cluster)
        attrs['deployment_mode'] = cluster.mode
        attrs['deployment_id'] = cluster.id
        attrs['openstack_version'] = release.version
        attrs['fuel_version'] = cluster.fuel_version
        attrs.update(
            objects.Release.get_orchestrator_data_dict(release)
        )
        attrs['nodes'] = cls.node_list(get_nodes_not_for_deletion(cluster))

        for node in attrs['nodes']:
            if node['role'] in 'cinder':
                attrs['use_cinder'] = True

        # default value for glance
        attrs['storage']['pg_num'] = 128

        cls.set_primary_mongo(attrs['nodes'])

        attrs = dict_merge(
            attrs,
            cls.get_net_provider_serializer(cluster).get_common_attrs(cluster,
                                                                      attrs))

        # plugins hooks
        attrs = rpc_hooks.process_cluster_attrs(cluster, attrs)

        return attrs

    @classmethod
    def current_release(cls, cluster):
        """Actual cluster release."""
        return objects.Release.get_by_uid(cluster.pending_release_id) \
            if cluster.status == consts.CLUSTER_STATUSES.update \
            else cluster.release

    @classmethod
    def set_storage_parameters(cls, cluster, attrs):
        """Generate pg_num as the number of OSDs across the cluster
        multiplied by 100, divided by Ceph replication factor, and
        rounded up to the nearest power of 2.
        """
        osd_num = 0
        nodes = db().query(Node). \
            filter(or_(
                Node.role_list.any(name='ceph-osd'),
                Node.pending_role_list.any(name='ceph-osd'))). \
            filter(Node.cluster == cluster). \
            options(joinedload('attributes'))
        for node in nodes:
            for disk in node.attributes.volumes:
                for part in disk.get('volumes', []):
                    if part.get('name') == 'ceph' and part.get('size', 0) > 0:
                        osd_num += 1
        if osd_num > 0:
            repl = int(attrs['storage']['osd_pool_size'])
            pg_num = 2 ** int(math.ceil(math.log(osd_num * 100.0 / repl, 2)))
        else:
            pg_num = 128
        attrs['storage']['pg_num'] = pg_num

        return attrs

    @classmethod
    def node_list(cls, nodes):
        """Generate nodes list. Represents
        as "nodes" parameter in facts.
        """
        node_list = []

        for node in nodes:
            for role in sorted(objects.Node.get_all_roles(node)):
                node_list.append({
                    'uid': node.uid,
                    'fqdn': node.fqdn,
                    'name': objects.Node.make_slave_name(node),
                    'role': role})

        return node_list

    @classmethod
    def by_role(cls, nodes, role):
        return filter(lambda node: node['role'] == role, nodes)

    @classmethod
    def not_roles(cls, nodes, roles):
        return filter(lambda node: node['role'] not in roles, nodes)

    @classmethod
    def set_deployment_priorities(cls, nodes):
        """Set priorities of deployment."""
        prior = Priority()

        for n in cls.by_role(nodes, 'zabbix-server'):
            n['priority'] = prior.next

        for n in cls.by_role(nodes, 'mongo'):
            n['priority'] = prior.next

        for n in cls.by_role(nodes, 'primary-mongo'):
            n['priority'] = prior.next

        for n in cls.by_role(nodes, 'controller'):
            n['priority'] = prior.next

        other_nodes_prior = prior.next
        for n in cls.not_roles(nodes, ['controller',
                                       'mongo',
                                       'primary-mongo',
                                       'zabbix-server']):
            n['priority'] = other_nodes_prior

    @classmethod
    def set_critical_nodes(cls, cluster, nodes):
        """Set behavior on nodes deployment error
        during deployment process.
        """
        for n in nodes:
            n['fail_if_error'] = n['role'] in cls.critical_roles

    @classmethod
    def serialize_nodes(cls, nodes):
        """Serialize node for each role.
        For example if node has two roles then
        in orchestrator will be passed two serialized
        nodes.
        """
        serialized_nodes = []
        for node in nodes:
            for role in sorted(objects.Node.get_all_roles(node)):
                serialized_nodes.append(cls.serialize_node(node, role))
        cls.set_primary_mongo(serialized_nodes)
        return serialized_nodes

    @classmethod
    def serialize_node(cls, node, role):
        """Serialize node, then it will be
        merged with common attributes
        """
        node_attrs = {
            # Yes, uid is really should be a string
            'uid': node.uid,
            'fqdn': node.fqdn,
            'status': node.status,
            'role': role,
            # TODO (eli): need to remove, requried
            # for the fake thread only
            'online': node.online
        }

        node_attrs.update(
            cls.get_net_provider_serializer(node.cluster).get_node_attrs(node))
        node_attrs.update(cls.get_image_cache_max_size(node))
        node_attrs.update(cls.generate_test_vm_image_data(node))

        # plugins hooks
        node_attrs = rpc_hooks.process_node_attrs(node, node_attrs)

        return node_attrs

    @classmethod
    def get_image_cache_max_size(cls, node):
        return {
            'glance': {
                'image_cache_max_size': volume_manager.calc_glance_cache_size(
                    node.attributes.volumes
                )
            }
        }

    @classmethod
    def generate_test_vm_image_data(cls, node):
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
        # Add default Glance property for Murano.
        glance_properties = [
            """--property murano_image_info="""
            """'{"title": "Murano Demo", "type": "cirros.demo"}'"""
        ]

        # Alternate VMWare specific values.
        if c_attrs['editable']['common']['libvirt_type']['value'] == 'vcenter':
            image_data.update({
                'disk_format': 'vmdk',
                'img_path': '{0}cirros-i386-disk.vmdk'.format(img_dir),
            })
            glance_properties.append('--property vmware_disktype=sparse')
            glance_properties.append('--property vmware_adaptertype=lsiLogic')
            glance_properties.append('--property hypervisor_type=vmware')

        image_data['glance_properties'] = ' '.join(glance_properties)

        return {'test_vm_image': image_data}

    @classmethod
    def set_primary_node(cls, nodes, role, primary_node_index):
        """Set primary node for role if it not set yet.
        primary_node_index defines primary node position in nodes list
        """
        sorted_nodes = sorted(
            nodes, key=lambda node: int(node['uid']))

        primary_role = 'primary-{0}'.format(role)
        primary_node = cls.filter_by_roles(
            sorted_nodes, [primary_role])
        if primary_node:
            return

        result_nodes = cls.filter_by_roles(
            sorted_nodes, [role])
        if result_nodes:
            result_nodes[primary_node_index]['role'] = primary_role

    @classmethod
    def set_primary_mongo(cls, nodes):
        """Set primary mongo for the last mongo node
        node if it not set yet
        """
        cls.set_primary_node(nodes, 'mongo', 0)

    @classmethod
    def filter_by_roles(cls, nodes, roles):
        return filter(
            lambda node: node['role'] in roles, nodes)


class DeploymentHASerializer(DeploymentMultinodeSerializer):
    """Serializer for ha mode."""

    critical_roles = ['primary-controller',
                      'primary-mongo',
                      'primary-swift-proxy',
                      'ceph-osd']

    @classmethod
    def serialize_nodes(cls, nodes):
        """Serialize nodes and set primary-controller
        """
        serialized_nodes = super(
            DeploymentHASerializer, cls).serialize_nodes(nodes)
        cls.set_primary_controller(serialized_nodes)
        return serialized_nodes

    @classmethod
    def set_primary_controller(cls, nodes):
        """Set primary controller for the first controller
        node if it not set yet
        """
        cls.set_primary_node(nodes, 'controller', 0)

    @classmethod
    def get_last_controller(cls, nodes):
        sorted_nodes = sorted(
            nodes, key=lambda node: int(node['uid']))

        controller_nodes = cls.filter_by_roles(
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

    @classmethod
    def get_common_attrs(cls, cluster):
        """Common attributes for all facts
        """
        common_attrs = super(
            DeploymentHASerializer,
            cls
        ).get_common_attrs(cluster)

        net_manager = objects.Cluster.get_network_manager(cluster)

        for ng in cluster.network_groups:
            if ng.meta.get("assign_vip"):
                common_attrs[ng.name + '_vip'] = net_manager.assign_vip(
                    cluster.id, ng.name)

        common_attrs['mp'] = [
            {'point': '1', 'weight': '1'},
            {'point': '2', 'weight': '2'}]

        last_controller = cls.get_last_controller(common_attrs['nodes'])
        common_attrs.update(last_controller)

        # Assign primary controller in nodes list
        cls.set_primary_controller(common_attrs['nodes'])

        return common_attrs

    @classmethod
    def set_deployment_priorities(cls, nodes):
        """Set priorities of deployment for HA mode."""
        prior = Priority()

        zabbix_server_prior = prior.next
        for n in cls.by_role(nodes, 'zabbix-server'):
            n['priority'] = zabbix_server_prior

        primary_swift_proxy_piror = prior.next
        for n in cls.by_role(nodes, 'primary-swift-proxy'):
            n['priority'] = primary_swift_proxy_piror

        swift_proxy_prior = prior.next
        for n in cls.by_role(nodes, 'swift-proxy'):
            n['priority'] = swift_proxy_prior

        storage_prior = prior.next
        for n in cls.by_role(nodes, 'storage'):
            n['priority'] = storage_prior

        for n in cls.by_role(nodes, 'mongo'):
            n['priority'] = prior.next

        for n in cls.by_role(nodes, 'primary-mongo'):
            n['priority'] = prior.next

        # Deploy primary-controller
        if not cls.by_role(nodes, 'primary-controller'):
            cls.set_primary_controller(nodes)
        for n in cls.by_role(nodes, 'primary-controller'):
            n['priority'] = prior.next

        # Then deploy other controllers.
        # We are deploying in parallel, so do
        # not let us deploy more than 6 controllers
        # simultaneously or galera master may be exhausted

        secondary_controllers = cls.by_role(nodes, 'controller')

        for index, node in enumerate(secondary_controllers):
            if index % 6 == 0:
                sec_controller_priority = prior.next
            node['priority'] = sec_controller_priority

        other_nodes_prior = prior.next
        for n in cls.not_roles(nodes, ['primary-swift-proxy',
                                       'swift-proxy',
                                       'storage',
                                       'primary-controller',
                                       'controller',
                                       'quantum',
                                       'mongo',
                                       'primary-mongo',
                                       'zabbix-server']):
            n['priority'] = other_nodes_prior




def serialize(cluster, nodes, ignore_customized=False):
    """Serialization depends on deployment mode
    """
    objects.NodeCollection.prepare_for_deployment(cluster.nodes)

    if cluster.mode == 'multinode':
        serializer = DeploymentMultinodeSerializer
    elif cluster.is_ha_mode:
        serializer = DeploymentHASerializer

    return serializer.serialize(
        cluster, nodes, ignore_customized=ignore_customized)
