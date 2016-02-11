# -*- coding: utf-8 -*-

#    Copyright 2015 Mirantis, Inc.
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

import collections
import copy
import mock
import netaddr
import six
import yaml

from oslo_serialization import jsonutils

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun.network.manager import NetworkManager
from nailgun import objects
from nailgun.orchestrator import stages
from nailgun.test import base
from nailgun.utils import reverse

from nailgun.orchestrator.deployment_graph import AstuteGraph
from nailgun.orchestrator.deployment_serializers import \
    get_serializer_for_cluster
from nailgun.orchestrator.neutron_serializers import \
    NeutronNetworkDeploymentSerializer70
from nailgun.orchestrator.neutron_serializers import \
    NeutronNetworkTemplateSerializer70
from nailgun.test.integration.test_orchestrator_serializer import \
    BaseDeploymentSerializer
from nailgun.test.integration.test_orchestrator_serializer import \
    TestDeploymentHASerializer61
from nailgun.test.integration.test_orchestrator_serializer import \
    TestNovaOrchestratorSerializer
from nailgun.test.integration.test_orchestrator_serializer import \
    TestSerializeInterfaceDriversData


class PrepareDataMixin(object):

    def patch_net_roles_for_release(self):
        rel_id = self.env.create_release(version=self.env_version).id
        rel_db = self.db.query(models.Release).filter_by(id=rel_id).one()

        to_patch = yaml.safe_load("""
      -
        id: "keystone/api"
        default_mapping: "management"
        properties: &default_network_roles_metadata_properties
          subnet: true
          gateway: false
          vip: []
      -
        id: "admin/pxe"
        default_mapping: "fuelweb_admin"
        properties:
          subnet: true
          gateway: true
          vip: []
      -
        id: "swift/api"
        default_mapping: "management"
        properties: *default_network_roles_metadata_properties
      -
        id: "neutron/api"
        default_mapping: "management"
        properties: *default_network_roles_metadata_properties
      -
        id: "sahara/api"
        default_mapping: "management"
        properties: *default_network_roles_metadata_properties
      -
        id: "aodh/api"
        default_mapping: "management"
        properties: *default_network_roles_metadata_properties
      -
        id: "ceilometer/api"
        default_mapping: "management"
        properties: *default_network_roles_metadata_properties
      -
        id: "cinder/api"
        default_mapping: "management"
        properties: *default_network_roles_metadata_properties
      -
        id: "glance/api"
        default_mapping: "management"
        properties: *default_network_roles_metadata_properties
      -
        id: "heat/api"
        default_mapping: "management"
        properties: *default_network_roles_metadata_properties
      -
        id: "nova/api"
        default_mapping: "management"
        properties: *default_network_roles_metadata_properties
      -
        id: "murano/api"
        default_mapping: "management"
        properties: *default_network_roles_metadata_properties
      -
        id: "horizon"
        default_mapping: "management"
        properties: *default_network_roles_metadata_properties
      -
        id: "mgmt/memcache"
        default_mapping: "management"
        properties: *default_network_roles_metadata_properties
      -
        id: "mgmt/database"
        default_mapping: "management"
        properties: *default_network_roles_metadata_properties
      -
        id: "mgmt/messaging"
        default_mapping: "management"
        properties: *default_network_roles_metadata_properties
      -
        id: "mgmt/corosync"
        default_mapping: "management"
        properties: *default_network_roles_metadata_properties
      -
        id: "mgmt/vip"
        default_mapping: "management"
        properties:
          subnet: true
          gateway: false
          vip:
            -
              name: "vrouter"
              namespace: "vrouter"
              alias: "management_vrouter_vip"
            -
              name: "management"
              namespace: "haproxy"
              alias: "management_vip"
      -
        id: "public/vip"
        default_mapping: "public"
        properties:
          subnet: true
          gateway: true
          vip:
            -
              name: "vrouter_pub"
              namespace: "vrouter"
              alias: "public_vrouter_vip"
            -
              name: "public"
              namespace: "haproxy"
              alias: "public_vip"
      -
        id: "neutron/private"
        default_mapping: "private"
        properties:
          subnet: false
          gateway: false
          vip: []
      -
        id: "neutron/mesh"
        default_mapping: "private"
        properties: *default_network_roles_metadata_properties
      -
        id: "neutron/floating"
        default_mapping: "public"
        properties:
          subnet: false
          gateway: false
          vip: []
      -
        id: "swift/replication"
        default_mapping: "storage"
        properties: *default_network_roles_metadata_properties
      -
        id: "ceph/public"
        default_mapping: "management"
        properties: *default_network_roles_metadata_properties
      -
        id: "ceph/radosgw"
        default_mapping: "public"
        properties: *default_network_roles_metadata_properties
      -
        id: "ceph/replication"
        default_mapping: "storage"
        properties: *default_network_roles_metadata_properties
      -
        id: "cinder/iscsi"
        default_mapping: "storage"
        properties: *default_network_roles_metadata_properties
      -
        id: "mongo/db"
        default_mapping: "management"
        properties: *default_network_roles_metadata_properties
      -
        id: "fw-admin"
        default_mapping: "fuelweb_admin"
        properties:
          subnet: true
          gateway: true
          vip: []
      -
        id: "management"
        default_mapping: "management"
        properties: *default_network_roles_metadata_properties
      -
        id: "ex"
        default_mapping: "public"
        properties:
          subnet: true
          gateway: true
          vip: []
      -
        id: "storage"
        default_mapping: "storage"
        properties: *default_network_roles_metadata_properties
      -
        id: "nova/migration"
        default_mapping: "management"
        properties: *default_network_roles_metadata_properties
        """)
        rel_db.network_roles_metadata = to_patch
        self.db.flush()
        return rel_db


class BaseTestDeploymentAttributesSerialization70(BaseDeploymentSerializer,
                                                  PrepareDataMixin):
    management = ['keystone/api', 'neutron/api', 'swift/api', 'sahara/api',
                  'aodh/api', 'ceilometer/api', 'cinder/api', 'glance/api',
                  'heat/api', 'nova/api', 'murano/api', 'horizon',
                  'management', 'mgmt/database', 'mgmt/messaging',
                  'mgmt/corosync', 'mgmt/memcache', 'mgmt/vip', 'mongo/db',
                  'ceph/public', 'nova/migration']
    fuelweb_admin = ['admin/pxe', 'fw-admin']
    neutron = ['neutron/private', 'neutron/floating']
    storage = ['storage', 'ceph/replication', 'swift/replication',
               'cinder/iscsi']
    public = ['ex', 'public/vip', 'ceph/radosgw']
    private = ['neutron/mesh']

    networks = ['fuelweb_admin', 'storage', 'management', 'public', 'private']

    # Must be set in subclasses
    segmentation_type = None
    env_version = '2015.1.0-7.0'

    def setUp(self):
        super(BaseTestDeploymentAttributesSerialization70, self).setUp()
        self.cluster = self.create_env(consts.CLUSTER_MODES.ha_compact)

        objects.Cluster.prepare_for_deployment(self.env.clusters[-1])
        self.cluster_db = self.db.query(models.Cluster).get(self.cluster['id'])
        serializer_type = get_serializer_for_cluster(self.cluster_db)
        self.serializer = serializer_type(AstuteGraph(self.cluster_db))
        self.serialized_for_astute = self.serializer.serialize(
            self.cluster_db, self.cluster_db.nodes)
        self.vm_data = self.env.read_fixtures(['vmware_attributes'])

    def create_env(self, mode):
        release = self.patch_net_roles_for_release()

        return self.env.create(
            cluster_kwargs={
                'release_id': release.id,
                'mode': mode,
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': self.segmentation_type},
            nodes_kwargs=[
                {'roles': ['controller'],
                 'pending_addition': True},
                {'roles': ['compute'],
                 'pending_addition': True}])

    def check_vips_serialized(self, node_data):
        vips_names = ['vrouter', 'management', 'vrouter_pub', 'public']
        # check that vip-related info is not in root
        self.assertTrue(all(vip_name not in node_data
                            for vip_name in vips_names))
        vips_data = node_data['network_metadata']['vips']
        self.assertItemsEqual(vips_data,
                              vips_names)
        for vip in vips_names:
            self.assertItemsEqual(
                vips_data[vip],
                ['network_role', 'namespace', 'ipaddr', 'node_roles']
            )


class TestDeploymentAttributesSerialization70(
    BaseTestDeploymentAttributesSerialization70
):
    segmentation_type = consts.NEUTRON_SEGMENT_TYPES.vlan
    custom_network = {
        'name': 'custom',
        'role': 'plugin/custom',
        'cidr': '192.168.3.0/24',
        'vlan_start': 50,
        'bridge': 'br-custom',
    }
    plugin_network_roles = yaml.safe_load("""
- id: "{role}"
  default_mapping: "{name}"
  properties:
    subnet: true
    gateway: false
    vip:
       - name: "{name}"
         namespace: "haproxy"
    """.format(**custom_network))

    def test_non_default_bridge_mapping(self):
        expected_mapping = {
            u'test': u'br-test',
            u'testnetwork1': u'br-testnetwork',
            u'testnetwork13': u'br-testnetwork',
            u'my-super-network': u'br-my-super-net',
            u'uplink-network-east': u'br-uplink-netw',
            u'uplink-network-west': u'br-uplink-netw',
            u'uplink-network-south': u'br-uplink-netw',
            u'12345uplink-network-south': u'br-12345uplink',
            u'fw-admin': u'br-fw-admi'
        }
        cluster = self.env.create(
            cluster_kwargs={
                'release_id': self.env.releases[0].id,
                'mode': consts.CLUSTER_MODES.ha_compact,
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': self.segmentation_type})
        self.cluster_db = objects.Cluster.get_by_uid(cluster['id'])
        for name in expected_mapping:
            self.env._create_network_group(cluster=self.cluster_db,
                                           name=name)
        self.env.create_node(
            api=True,
            cluster_id=cluster['id'],
            pending_roles=['controller'],
            pending_addition=True)
        net_serializer = self.serializer.get_net_provider_serializer(
            self.cluster_db)
        objects.Cluster.prepare_for_deployment(self.cluster_db)
        mapping = net_serializer.get_node_non_default_bridge_mapping(
            self.cluster_db.nodes[0])

        # since we have a suffix generation for bridges, they may have
        # different suffix based on PYTHONHASHSEED. hence, we can't
        # come up with a normal dictionary comparison. so let's
        # compare that all bridges are unique, and they are unique
        # for networks which may have bridge collision.
        br_collision = collections.defaultdict(list)
        self.assertEqual(len(mapping), len(expected_mapping))
        self.assertEqual(len(expected_mapping), len(set(mapping.values())))

        for netname in expected_mapping:
            # check that bridge name has been generated from the network
            self.assertTrue(
                mapping[netname].startswith(expected_mapping[netname]))

            br_collision[expected_mapping[netname]].append(netname)

        # check that there's no collision between networks
        for bridge, netnames in six.iteritems(br_collision):
            bridges = set((mapping[netname] for netname in netnames))
            self.assertEqual(len(bridges), len(netnames))

    def test_network_scheme_custom_networks(self):
        cluster = self.env.create(
            cluster_kwargs={
                'release_id': self.env.releases[0].id,
                'mode': consts.CLUSTER_MODES.ha_compact,
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': self.segmentation_type})
        self.cluster_db = objects.Cluster.get_by_uid(cluster['id'])
        self.env._create_network_group(cluster=self.cluster_db,
                                       name=self.custom_network['name'],
                                       cidr=self.custom_network['cidr'],
                                       vlan_start=self.custom_network[
                                           'vlan_start'
                                       ])
        self.env._add_plugin_network_roles(self.cluster_db,
                                           self.plugin_network_roles)
        self.env.create_node(
            api=True,
            cluster_id=cluster['id'],
            pending_roles=['controller'],
            pending_addition=True)
        objects.Cluster.prepare_for_deployment(self.cluster_db)
        serializer_type = get_serializer_for_cluster(self.cluster_db)
        serializer = serializer_type(AstuteGraph(self.cluster_db))
        serialized_for_astute = serializer.serialize(
            self.cluster_db, self.cluster_db.nodes)
        for node in serialized_for_astute:
            vips = node['network_metadata']['vips']
            roles = node['network_scheme']['roles']
            transformations = node['network_scheme']['transformations']
            node_network_roles = (node['network_metadata']['nodes']
                                  ['node-' + node['uid']]['network_roles'])
            custom_ip = node_network_roles.get(self.custom_network['role'],
                                               '0.0.0.0')
            custom_brs = filter(lambda t: t.get('name') ==
                                self.custom_network['bridge'],
                                transformations)
            custom_ports = filter(lambda t: t.get('name') ==
                                  ("eth0.%s" %
                                   self.custom_network['vlan_start']),
                                  transformations)
            self.assertEqual(roles.get(self.custom_network['role']),
                             self.custom_network['bridge'])
            self.assertEqual(vips.get(self.custom_network['name'],
                                      {}).get('network_role'),
                             self.custom_network['role'])
            self.assertTrue(netaddr.IPAddress(custom_ip) in
                            netaddr.IPNetwork(self.custom_network['cidr']))
            self.assertEqual(len(custom_brs), 1)
            self.assertEqual(len(custom_ports), 1)
            self.assertEqual(custom_ports[0]['bridge'],
                             self.custom_network['bridge'])

    def test_network_scheme(self):
        for node in self.serialized_for_astute:
            roles = node['network_scheme']['roles']
            node = objects.Node.get_by_uid(node['uid'])

            expected_roles = zip(
                self.management, ['br-mgmt'] * len(self.management))
            expected_roles += zip(
                self.fuelweb_admin, ['br-fw-admin'] * len(self.fuelweb_admin))
            expected_roles += zip(
                self.storage, ['br-storage'] * len(self.storage))

            if objects.Node.should_have_public(node):
                expected_roles += zip(
                    self.public, ['br-ex'] * len(self.public))
                expected_roles += [('neutron/floating', 'br-floating')]

            if node.cluster.network_config.segmentation_type == \
                    consts.NEUTRON_SEGMENT_TYPES.vlan:
                expected_roles += [('neutron/private', 'br-prv')]

            if node.cluster.network_config.segmentation_type in \
                    (consts.NEUTRON_SEGMENT_TYPES.gre,
                     consts.NEUTRON_SEGMENT_TYPES.tun):
                expected_roles += [('neutron/mesh', 'br-mesh')]

            self.assertEqual(roles, dict(expected_roles))

    def test_offloading_modes_serialize(self):
        meta = self.env.default_metadata()
        changed_offloading_modes = {}
        for interface in meta['interfaces']:
            changed_offloading_modes[interface['name']] = \
                NetworkManager._get_modified_offloading_modes(
                    interface.get('offloading_modes'))

        for node in self.serialized_for_astute:
            interfaces = node['network_scheme']['interfaces']
            for iface_name in interfaces:
                ethtool_blk = interfaces[iface_name].get('ethtool', None)
                self.assertIsNotNone(
                    ethtool_blk,
                    "There is no 'ethtool' block in deployment data")
                offload_blk = ethtool_blk.get('offload', None)
                self.assertIsNotNone(
                    offload_blk,
                    "There is no 'offload' block in deployment data")
                self.assertDictEqual(offload_blk,
                                     changed_offloading_modes[iface_name])

    def test_network_metadata(self):
        neutron_serializer = self.serializer.get_net_provider_serializer(
            self.cluster_db)
        for node_data in self.serialized_for_astute:
            self.assertItemsEqual(
                node_data['network_metadata'], ['nodes', 'vips'])
            for k, v in six.iteritems(node_data['network_metadata']['nodes']):
                self.assertItemsEqual(
                    v,
                    ['uid', 'fqdn', 'name', 'user_node_name',
                     'swift_zone', 'node_roles', 'network_roles']
                )
                node = objects.Node.get_by_uid(v['uid'])
                ip_by_net = neutron_serializer.get_network_to_ip_mapping(node)

                self.assertEqual(objects.Node.get_slave_name(node), k)
                self.assertEqual(v['uid'], node.uid)
                self.assertEqual(v['fqdn'], objects.Node.get_node_fqdn(node))
                self.assertEqual(v['name'], k)
                self.assertEqual(v['user_node_name'], node.name)
                self.assertEqual(v['swift_zone'], node.uid)

                network_roles = zip(self.management,
                                    [ip_by_net['management']] * len(
                                        self.management))
                network_roles += zip(self.fuelweb_admin,
                                     [ip_by_net['fuelweb_admin']] * len(
                                         self.fuelweb_admin))
                network_roles += zip(
                    self.storage, [ip_by_net['storage']] * len(self.storage))
                network_roles += zip(self.neutron, [None] * len(self.neutron))

                if objects.Node.should_have_public(node):
                    network_roles += zip(
                        self.public, [ip_by_net['public']] * len(self.public))

                if node.cluster.network_config.segmentation_type in \
                        (consts.NEUTRON_SEGMENT_TYPES.gre,
                         consts.NEUTRON_SEGMENT_TYPES.tun):
                    network_roles += zip(
                        self.private,
                        [ip_by_net['private']] * len(self.private))

                self.assertEqual(v['network_roles'], dict(network_roles))
            self.check_vips_serialized(node_data)

    def test_generate_vmware_attributes_data(self):
        self.check_generate_vmware_attributes_data()

        result = self.serializer.serialize_node(
            self.env.nodes[0], 'compute-vmware')

        self.assertEqual(
            result['vcenter']['computes'][0]['target_node'],
            "test_target_node")
        self.assertEqual(
            result['vcenter']['computes'][2]['target_node'],
            "controllers")


class TestDeploymentAttributesSerializationSegmentationGre70(
    TestDeploymentAttributesSerialization70
):
    segmentation_type = consts.NEUTRON_SEGMENT_TYPES.gre


class TestDeploymentAttributesSerializationSegmentationTun70(
    TestDeploymentAttributesSerialization70
):
    segmentation_type = consts.NEUTRON_SEGMENT_TYPES.tun


class TestDeploymentSerializationForNovaNetwork70(
    BaseTestDeploymentAttributesSerialization70
):

    def create_env(self, mode):
        release = self.patch_net_roles_for_release()
        return self.env.create(
            cluster_kwargs={
                'release_id': release.id,
                'mode': mode,
                'net_provider': consts.CLUSTER_NET_PROVIDERS.nova_network},
            nodes_kwargs=[
                {'roles': ['controller'],
                 'pending_addition': True,
                 'name': self.node_name,
                 }
            ])

    def test_network_scheme(self):
        for node in self.serialized_for_astute:
            roles = node['network_scheme']['roles']
            expected_roles = {
                'admin/pxe': 'br-fw-admin',

                'keystone/api': 'br-mgmt',
                'swift/api': 'br-mgmt',
                'sahara/api': 'br-mgmt',
                'aodh/api': 'br-mgmt',
                'ceilometer/api': 'br-mgmt',
                'cinder/api': 'br-mgmt',
                'glance/api': 'br-mgmt',
                'heat/api': 'br-mgmt',
                'nova/api': 'br-mgmt',
                'murano/api': 'br-mgmt',
                'horizon': 'br-mgmt',

                'mgmt/database': 'br-mgmt',
                'mgmt/messaging': 'br-mgmt',
                'mgmt/corosync': 'br-mgmt',
                'mgmt/memcache': 'br-mgmt',
                'mgmt/vip': 'br-mgmt',

                'public/vip': 'br-ex',

                'swift/replication': 'br-storage',

                'ceph/public': 'br-mgmt',
                'ceph/radosgw': 'br-ex',
                'ceph/replication': 'br-storage',

                'cinder/iscsi': 'br-storage',

                'mongo/db': 'br-mgmt',

                'novanetwork/fixed': 'eth0.103',

                # deprecated
                'fw-admin': 'br-fw-admin',
                'management': 'br-mgmt',
                'ex': 'br-ex',
                'storage': 'br-storage',
            }
            self.assertEqual(roles, expected_roles)

    def test_network_metadata(self):
        nm = objects.Cluster.get_network_manager(self.env.clusters[0])
        ip_by_net = {
            'fuelweb_admin': None,
            'storage': None,
            'management': None,
            'public': None
        }
        node = self.env.nodes[0]
        networks = nm.get_node_networks(node)
        for net in ip_by_net:
            netgroup = nm.get_network_by_netname(net, networks)
            if netgroup.get('ip'):
                ip_by_net[net] = netgroup['ip'].split('/')[0]
        for node_data in self.serialized_for_astute:
            self.assertItemsEqual(
                node_data['network_metadata'], ['nodes', 'vips'])
            nodes = node_data['network_metadata']['nodes']
            for node_name, node_attrs in nodes.items():
                self.assertItemsEqual(
                    node_attrs,
                    ['uid', 'fqdn', 'name', 'user_node_name',
                     'swift_zone', 'node_roles', 'network_roles']
                )
                self.assertEqual(objects.Node.get_slave_name(node), node_name)
                self.assertEqual(node_attrs['uid'], node.uid)
                self.assertEqual(node_attrs['fqdn'],
                                 objects.Node.get_node_fqdn(node))
                self.assertEqual(node_attrs['name'], node_name)
                self.assertEqual(node_attrs['user_node_name'], node.name)
                self.assertEqual(node_attrs['swift_zone'], node.uid)

                network_roles = {
                    'admin/pxe': ip_by_net['fuelweb_admin'],
                    'fw-admin': ip_by_net['fuelweb_admin'],

                    'keystone/api': ip_by_net['management'],
                    'swift/api': ip_by_net['management'],
                    'sahara/api': ip_by_net['management'],
                    'aodh/api': ip_by_net['management'],
                    'ceilometer/api': ip_by_net['management'],
                    'cinder/api': ip_by_net['management'],
                    'glance/api': ip_by_net['management'],
                    'heat/api': ip_by_net['management'],
                    'nova/api': ip_by_net['management'],
                    'murano/api': ip_by_net['management'],
                    'horizon': ip_by_net['management'],

                    'management': ip_by_net['management'],
                    'mgmt/database': ip_by_net['management'],
                    'mgmt/messaging': ip_by_net['management'],
                    'mgmt/corosync': ip_by_net['management'],
                    'mgmt/memcache': ip_by_net['management'],
                    'mgmt/vip': ip_by_net['management'],

                    'mongo/db': ip_by_net['management'],

                    'ceph/public': ip_by_net['management'],

                    'storage': ip_by_net['storage'],
                    'ceph/replication': ip_by_net['storage'],
                    'swift/replication': ip_by_net['storage'],
                    'cinder/iscsi': ip_by_net['storage'],

                    'ex': ip_by_net['public'],
                    'public/vip': ip_by_net['public'],
                    'ceph/radosgw': ip_by_net['public'],
                }
                self.assertEqual(
                    node_attrs['network_roles'],
                    network_roles
                )
            self.check_vips_serialized(node_data)

    def test_generate_vmware_attributes_data(self):
        self.check_generate_vmware_attributes_data()

        result = self.serializer.serialize_node(
            self.env.nodes[0], 'compute-vmware')

        self.assertEqual(
            result['vcenter']['computes'][0]['target_node'],
            "test_target_node")
        self.assertEqual(
            result['vcenter']['computes'][2]['target_node'],
            "controllers")


class TestPluginDeploymentTasksInjection(base.BaseIntegrationTest):

    release_deployment_tasks = [
        {'id': 'pre_deployment_start',
         'type': 'stage'},
        {'id': 'pre_deployment_end',
         'type': 'stage',
         'requires': ['pre_deployment_start']},
        {'id': 'deploy_start',
         'type': 'stage'},
        {'id': 'deploy_end',
         'requires': ['deploy_start'],
         'type': 'stage'},
        {'id': 'post_deployment_start',
         'type': 'stage',
         'requires': ['deploy_end']},
        {'id': 'post_deployment_end',
         'type': 'stage',
         'requires': ['post_deployment_start']},
        {'id': 'primary-controller',
         'parameters': {'strategy': {'type': 'one_by_one'}},
         'required_for': ['deploy_end'],
         'requires': ['deploy_start'],
         'role': ['primary-controller'],
         'type': 'group'},
        {'id': 'first-fake-depl-task',
         'required_for': ['deploy_end'],
         'requires': ['deploy_start'],
         'type': 'puppet',
         'parameters': {'puppet_manifest': 'first-fake-depl-task',
                        'puppet_modules': 'test',
                        'timeout': 0},
         'groups': ['primary-controller']},
        {'id': 'second-fake-depl-task',
         'required_for': ['deploy_end'],
         'requires': ['deploy_start'],
         'type': 'puppet',
         'parameters': {'puppet_manifest': 'second-fake-depl-task',
                        'puppet_modules': 'test',
                        'timeout': 0},
         'groups': ['primary-controller']},
    ]

    def setUp(self):
        super(TestPluginDeploymentTasksInjection, self).setUp()

        self.env.create(
            release_kwargs={'deployment_tasks': self.release_deployment_tasks},
            cluster_kwargs={
                'mode': consts.CLUSTER_MODES.ha_compact,
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': consts.NEUTRON_SEGMENT_TYPES.vlan,
            },
            nodes_kwargs=[
                {'roles': ['controller'], 'primary_roles': ['controller'],
                 'pending_addition': True}
            ]
        )

        self.cluster = self.env.clusters[0]

        self.plugin_data = {
            'releases': [
                {
                    'repository_path': 'plugin_test',
                    'version': self.cluster.release.version,
                    'os': self.cluster.release.operating_system.lower(),
                    'mode': ['ha', 'multinode'],
                    'deployment_scripts_path': 'plugin_test/'
                },
            ],
        }

    def prepare_plugins_for_cluster(self, cluster, plugins_kw_list):
        for kw in plugins_kw_list:
            kw.update(self.plugin_data)
            self.env.create_plugin(cluster=cluster, **kw)

    def _check_pre_deployment_tasks(self, serialized, task_type):
        self.assertTrue(serialized)

        needed_task = next(
            t for t in serialized
            if t['type'] == task_type)
        self.assertIsNotNone(needed_task)
        self.assertIsNotNone(needed_task.get('parameters'))
        self.assertItemsEqual(
            (n.uid for n in self.cluster.nodes),
            needed_task['uids']
        )

    def test_plugin_depl_tasks_proper_injections(self):
        self.prepare_plugins_for_cluster(
            self.cluster,
            [
                {
                    'name': 'between_rel_tasks',
                    'deployment_tasks': [
                        {
                            'id': 'between-rel-tasks',
                            'type': 'puppet',
                            'groups': ['primary-controller'],
                            'requires': ['first-fake-depl-task'],
                            'required_for': ['second-fake-depl-task'],
                            'parameters': {
                                'puppet_manifest': 'between-rel-tasks',
                                'puppet_modules': 'test',
                                'timeout': 0,
                            }
                        },
                    ],
                },
            ]
        )

        graph = AstuteGraph(self.cluster)
        objects.Cluster.prepare_for_deployment(self.cluster)
        serializer = \
            get_serializer_for_cluster(self.cluster)(graph)
        serialized = serializer.serialize(self.cluster, self.cluster.nodes)

        serialized_tasks = serialized[0]['tasks']

        expected_priority = {
            100: 'first-fake-depl-task',
            200: 'between-rel-tasks',
            300: 'second-fake-depl-task',
        }

        for task in serialized_tasks:
            task_identificator = task['parameters']['puppet_manifest']
            self.assertEqual(
                task_identificator, expected_priority[task['priority']]
            )

    def test_plugin_depl_task_overwrite_from_rel(self):
        self.prepare_plugins_for_cluster(
            self.cluster,
            [
                {
                    'name': 'between_rel_tasks',
                    'deployment_tasks': [
                        {
                            'id': 'first-fake-depl-task',
                            'type': 'puppet',
                            'groups': ['primary-controller'],
                            'requires': ['deploy_start'],
                            'required_for': ['second-fake-depl-task'],
                            'parameters': {
                                'puppet_manifest': 'plugin_task',
                                'puppet_modules': 'test',
                                'timeout': 0,
                            }
                        },
                    ],
                },
            ]
        )

        graph = AstuteGraph(self.cluster)
        objects.Cluster.prepare_for_deployment(self.cluster)
        serializer = \
            get_serializer_for_cluster(self.cluster)(graph)
        serialized = serializer.serialize(self.cluster, self.cluster.nodes)

        serialized_tasks = serialized[0]['tasks']

        needed_task_priority = next(
            t['priority'] for t in serialized_tasks
            if t['parameters']['puppet_manifest'] == 'plugin_task'
        )
        # first task in graph has priority equal 100
        self.assertEqual(needed_task_priority, 100)

    def test_plugin_depl_task_in_pre_depl(self):
        self.prepare_plugins_for_cluster(
            self.cluster,
            [
                {
                    'name': 'pre_depl_plugin_task',
                    'deployment_tasks': [
                        {
                            'id': 'pre-depl-plugin-task',
                            'type': 'puppet',
                            'role': ['primary-controller'],
                            'requires': ['pre_deployment_start'],
                            'required_for': ['pre_deployment_end'],
                            'parameters': {
                                'puppet_manifest': 'pre_depl_plugin_task',
                                'puppet_modules': 'test',
                                'timeout': 0,
                            }
                        },
                    ],
                },
            ]
        )

        graph = AstuteGraph(self.cluster)
        objects.Cluster.prepare_for_deployment(self.cluster)
        with mock.patch('nailgun.plugins.adapters.glob.glob',
                        mock.Mock(return_value='path/to/test/repos')):
            pre_deployment = stages.pre_deployment_serialize(
                graph, self.cluster, self.cluster.nodes)

        for task_type in (consts.ORCHESTRATOR_TASK_TYPES.sync,
                          consts.ORCHESTRATOR_TASK_TYPES.upload_file):
            self._check_pre_deployment_tasks(pre_deployment, task_type)

    def test_plugin_depl_task_for_master_not_in_pre_depl(self):
        self.prepare_plugins_for_cluster(
            self.cluster,
            [
                {
                    'name': 'pre_depl_plugin_task',
                    'deployment_tasks': [
                        {
                            'id': 'pre-depl-plugin-task',
                            'type': 'puppet',
                            'role': consts.MASTER_NODE_UID,
                            'requires': ['pre_deployment_start'],
                            'required_for': ['pre_deployment_end'],
                            'parameters': {
                                'puppet_manifest': 'pre_depl_plugin_task',
                                'puppet_modules': 'test',
                                'timeout': 0,
                            }
                        },
                    ],
                },
                {
                    'name': 'pre_depl_plugin_task_for_master_and_contr',
                    'deployment_tasks': [
                        {
                            'id': 'pre-depl-plugin-task-for-master-and-contr',
                            'type': 'puppet',
                            'groups': [consts.MASTER_NODE_UID,
                                       'primary-controller'],
                            'requires': ['pre_deployment_start'],
                            'required_for': ['pre_deployment_end'],
                            'parameters': {
                                'puppet_manifest': 'pre_depl_plugin_task',
                                'puppet_modules': 'test',
                                'timeout': 0,
                            }
                        },
                    ],
                },
            ]
        )

        graph = AstuteGraph(self.cluster)
        objects.Cluster.prepare_for_deployment(self.cluster)
        with mock.patch('nailgun.plugins.adapters.glob.glob',
                        mock.Mock(return_value='path/to/test/repos')):
            pre_deployment = stages.pre_deployment_serialize(
                graph, self.cluster, self.cluster.nodes)

        for st in pre_deployment:
            self.assertNotIn(consts.MASTER_NODE_UID, st['uids'])

    def test_plugin_depl_task_in_post_depl(self):
        self.prepare_plugins_for_cluster(
            self.cluster,
            [
                {
                    'name': 'post-depl-plugin-task',
                    'deployment_tasks': [
                        {
                            'id': 'post-depl-plugin-task',
                            'type': 'puppet',
                            'role': ['primary-controller'],
                            'requires': ['post_deployment_start'],
                            'required_for': ['post_deployment_end'],
                            'parameters': {
                                'puppet_manifest': 'post_depl_plugin_task',
                                'puppet_modules': 'test',
                                'timeout': 0,
                            }
                        },
                    ],
                },
            ]
        )

        graph = AstuteGraph(self.cluster)
        objects.Cluster.prepare_for_deployment(self.cluster)
        post_deployment = stages.post_deployment_serialize(
            graph, self.cluster, self.cluster.nodes)

        self.assertEqual(
            post_deployment[0]['parameters']['puppet_manifest'],
            'post_depl_plugin_task'
        )

    def test_process_skipped_task(self):
        self.prepare_plugins_for_cluster(
            self.cluster,
            [
                {
                    'name': 'task_with_skipped_plugin',
                    'deployment_tasks': [
                        {
                            'id': 'skipped_task',
                            'type': 'skipped',
                        },
                    ],
                },
            ]
        )

        graph = AstuteGraph(self.cluster)
        objects.Cluster.prepare_for_deployment(self.cluster)
        serializer = \
            get_serializer_for_cluster(self.cluster)(graph)
        serialized = serializer.serialize(self.cluster, self.cluster.nodes)

        tasks = serialized[0]['tasks']
        release_depl_tasks_ids = ('first-fake-depl-task',
                                  'second-fake-depl-task')

        serialized_tasks_ids = (t['parameters']['puppet_manifest']
                                for t in tasks)
        self.assertItemsEqual(release_depl_tasks_ids, serialized_tasks_ids)


class TestRolesSerializationWithPlugins(BaseDeploymentSerializer,
                                        PrepareDataMixin):

    env_version = '2015.1.0-7.0'

    ROLES = yaml.safe_load("""
        test_role:
          name: "Some plugin role"
          description: "Some description"
          conflicts:
            - some_not_compatible_role
          limits:
            min: 1
          restrictions:
            - condition: "some logic condition"
              message: "Some message for restriction warning"
          volumes_mapping:
            - {allocate_size: "min", id: "os"}
            - {allocate_size: "all", id: "role_volume_name"}
    """)

    DEPLOYMENT_TASKS = yaml.safe_load("""
        - id: test_role
          type: group
          role: [test_role]
          required_for: [deploy_end]
          requires: [deploy_start]
          parameters:
            strategy:
              type: one_by_one

        - id: deployment_task_id
          type: puppet
          groups: [test_role]
          required_for: [deploy_end]
          requires: [deploy_start]
          parameters:
            puppet_manifest: /path/to/manifests
            puppet_modules: /path/to/modules
            timeout: 3600
    """)

    def setUp(self):
        super(TestRolesSerializationWithPlugins, self).setUp()

        release = self.patch_net_roles_for_release()
        self.env.create(
            cluster_kwargs={
                'release_id': release.id,
                'mode': consts.CLUSTER_MODES.ha_compact,
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': consts.NEUTRON_SEGMENT_TYPES.vlan,
            })

        self.cluster = self.env.clusters[0]

        self.plugin_data = {
            'releases': [
                {
                    'repository_path': 'repositories/ubuntu',
                    'version': self.cluster.release.version,
                    'os': self.cluster.release.operating_system.lower(),
                    'mode': [self.cluster.mode],
                }
            ]
        }

    def _get_serializer(self, cluster):
        return get_serializer_for_cluster(cluster)(AstuteGraph(cluster))

    def test_tasks_were_serialized(self):
        plugin_data = {
            'roles_metadata': self.ROLES,
            'deployment_tasks': self.DEPLOYMENT_TASKS
        }
        plugin_data.update(self.plugin_data)
        self.env.create_plugin(cluster=self.cluster, **plugin_data)

        self.env.create_node(
            api=True,
            cluster_id=self.cluster.id,
            pending_roles=['test_role'],
            pending_addition=True)
        self.db.flush()

        objects.Cluster.prepare_for_deployment(self.cluster)

        serializer = self._get_serializer(self.cluster)
        serialized_data = serializer.serialize(
            self.cluster, self.cluster.nodes)
        self.assertItemsEqual(serialized_data[0]['tasks'], [{
            'parameters': {
                'cwd': '/etc/fuel/plugins/testing_plugin-0.1.0/',
                'puppet_manifest': '/path/to/manifests',
                'puppet_modules': '/path/to/modules',
                'timeout': 3600,
                'retries': None,
            },
            'priority': 100,
            'type': 'puppet',
            'uids': [self.cluster.nodes[0].uid],
            'id': 'deployment_task_id'
        }])

    def test_tasks_were_not_serialized(self):
        plugin_data = {
            'roles_metadata': {},
            'deployment_tasks': self.DEPLOYMENT_TASKS
        }
        plugin_data.update(self.plugin_data)
        self.env.create_plugin(cluster=self.cluster, **plugin_data)

        self.env.create_node(
            api=True,
            cluster_id=self.cluster.id,
            pending_roles=['controller'],
            pending_addition=True)
        self.db.flush()

        objects.Cluster.prepare_for_deployment(self.cluster)

        serializer = self._get_serializer(self.cluster)
        serialized_data = serializer.serialize(
            self.cluster, self.cluster.nodes)
        self.maxDiff = None
        self.assertItemsEqual(serialized_data[0]['tasks'], [
            {
                'parameters': {
                    'puppet_modules': '/etc/puppet/modules',
                    'puppet_manifest': '/etc/puppet/modules/osnailyfacter/'
                                       'modular/netconfig/netconfig.pp',
                    'timeout': 3600,
                    'retries': None,
                    'cwd': '/'},
                'priority': 100,
                'type': 'puppet',
                'id': 'netconfig',
                'uids': [self.cluster.nodes[0].uid],
            }, {
                'parameters': {
                    'cwd': '/',
                    'puppet_manifest': '/etc/puppet/manifests/site.pp',
                    'puppet_modules': '/etc/puppet/modules',
                    'timeout': 3600,
                    'retries': None},
                'priority': 200,
                'type': 'puppet',
                'id': 'deploy_legacy',
                'uids': [self.cluster.nodes[0].uid],
            }, {
                'parameters': {
                    'puppet_modules': '/etc/puppet/modules',
                    'puppet_manifest': '/etc/puppet/modules/osnailyfacter/'
                                       'modular/globals/globals.pp',
                    'timeout': 3600,
                    'retries': None,
                    'cwd': '/'},
                'priority': 300,
                'type': 'puppet',
                'id': 'globals',
                'uids': [self.cluster.nodes[0].uid],
            }])


class TestNetworkTemplateSerializer70(BaseDeploymentSerializer,
                                      PrepareDataMixin):

    env_version = '2015.1.0-7.0'

    def setUp(self, *args):
        super(TestNetworkTemplateSerializer70, self).setUp()
        self.cluster = self.create_env(consts.NEUTRON_SEGMENT_TYPES.vlan)
        self.net_template = self.env.read_fixtures(['network_template_70'])[0]

        objects.Cluster.set_network_template(
            self.cluster,
            self.net_template
        )
        cluster_db = self.db.query(models.Cluster).get(self.cluster['id'])
        objects.Cluster.prepare_for_deployment(cluster_db)

        serializer = get_serializer_for_cluster(self.cluster)
        self.serialized_for_astute = serializer(
            AstuteGraph(cluster_db)).serialize(self.cluster, cluster_db.nodes)

    def create_env(self, segment_type):
        release = self.patch_net_roles_for_release()
        cluster = self.env.create(
            cluster_kwargs={
                'api': False,
                'release_id': release.id,
                'mode': consts.CLUSTER_MODES.ha_compact,
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': segment_type},
        )
        nodes_kwargs = {
            'roles': ['controller'],
            'pending_addition': True,
            'name': self.node_name,
            'cluster_id': cluster['id']
        }
        self.env.create_nodes_w_interfaces_count(1, 4, **nodes_kwargs)
        nodes_kwargs['roles'] = ['compute', 'cinder']
        self.env.create_nodes_w_interfaces_count(1, 4, **nodes_kwargs)

        return cluster

    def create_more_nodes(self, iface_count=2):
        self.env.create_nodes_w_interfaces_count(
            1, iface_count, roles=['cinder'], cluster_id=self.cluster.id)
        self.env.create_nodes_w_interfaces_count(
            1, iface_count,
            roles=['cinder', 'controller'], cluster_id=self.cluster.id)
        self.env.create_nodes_w_interfaces_count(
            1, iface_count, roles=['compute'], cluster_id=self.cluster.id)

    def check_node_ips_on_certain_networks(self, node, net_names):
        ips = db().query(models.IPAddr).filter_by(node=node.id)
        self.assertEqual(ips.count(), len(net_names))
        for ip in ips:
            self.assertIn(ip.network_data.name, net_names)

    def test_get_net_provider_serializer(self):
        serializer = get_serializer_for_cluster(self.cluster)
        self.cluster.network_config.configuration_template = None

        net_serializer = serializer.get_net_provider_serializer(self.cluster)
        self.assertIs(net_serializer, NeutronNetworkDeploymentSerializer70)

        self.cluster.network_config.configuration_template = \
            self.net_template
        net_serializer = serializer.get_net_provider_serializer(self.cluster)
        self.assertIs(net_serializer, NeutronNetworkTemplateSerializer70)

    def test_ip_assignment_according_to_template(self):
        self.create_more_nodes(iface_count=4)
        # according to the template different node roles have different sets of
        # networks
        node_roles_vs_net_names = [
            (['controller'], ['public', 'management', 'fuelweb_admin']),
            (['compute'], ['management', 'fuelweb_admin']),
            (['cinder'], ['storage', 'management', 'fuelweb_admin']),
            (['compute', 'cinder'],
             ['storage', 'management', 'fuelweb_admin']),
            (['controller', 'cinder'],
             ['public', 'storage', 'management', 'fuelweb_admin'])]

        template_meta = self.net_template["adv_net_template"]["default"]
        # wipe out 'storage' template for 'compute' node role to make
        # node roles more distinct
        for node_role, template_list in six.iteritems(
                template_meta["templates_for_node_role"]):
            if node_role == 'compute':
                template_list.remove('storage')

        objects.Cluster.set_network_template(
            self.cluster,
            self.net_template
        )
        cluster_db = objects.Cluster.get_by_uid(self.cluster['id'])
        objects.Cluster.prepare_for_deployment(cluster_db)

        serializer = get_serializer_for_cluster(self.cluster)
        serialized_for_astute = serializer(
            AstuteGraph(cluster_db)).serialize(self.cluster, cluster_db.nodes)

        # 7 node roles on 5 nodes
        self.assertEqual(len(serialized_for_astute), 7)
        for node_data in serialized_for_astute:
            node = objects.Node.get_by_uid(node_data['uid'])
            for node_roles, net_names in node_roles_vs_net_names:
                if node.all_roles == set(node_roles):
                    self.check_node_ips_on_certain_networks(node, net_names)
                    break
            else:
                self.fail("Unexpected combination of node roles: {0}".format(
                    node.all_roles))

    def test_gateway_not_set_for_none_ip(self):
        attrs = copy.deepcopy(self.cluster.attributes.editable)
        attrs['neutron_advanced_configuration']['neutron_dvr']['value'] = True
        resp = self.app.patch(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': self.cluster.id}),
            params=jsonutils.dumps({'editable': attrs}),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        self.assertTrue(objects.Cluster.neutron_dvr_enabled(self.cluster))

        objects.Cluster.set_network_template(self.cluster, None)

        computes = filter(lambda n: 'compute' in n.roles, self.cluster.nodes)
        self.assertTrue(len(computes) > 0)
        compute = computes[0]

        serializer = get_serializer_for_cluster(self.cluster)
        net_serializer = serializer.get_net_provider_serializer(self.cluster)
        self.assertIs(net_serializer, NeutronNetworkDeploymentSerializer70)

        nm = objects.Cluster.get_network_manager(self.cluster)
        networks = nm.get_node_networks(compute)

        self.assertFalse(objects.Node.should_have_public_with_ip(compute))
        network_scheme = net_serializer.generate_network_scheme(
            compute, networks)
        self.assertNotIn('gateway', network_scheme['endpoints']['br-ex'])
        self.assertEqual('none', network_scheme['endpoints']['br-ex']['IP'])

    def test_public_iface_added_to_br_ex_in_dvr(self):
        attrs = copy.deepcopy(self.cluster.attributes.editable)
        attrs['neutron_advanced_configuration']['neutron_dvr']['value'] = True
        resp = self.app.patch(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': self.cluster.id}),
            params=jsonutils.dumps({'editable': attrs}),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        self.assertTrue(objects.Cluster.neutron_dvr_enabled(self.cluster))

        objects.Cluster.set_network_template(self.cluster, None)

        computes = filter(lambda n: 'compute' in n.roles, self.cluster.nodes)
        self.assertTrue(len(computes) > 0)
        compute = computes[0]

        serializer = get_serializer_for_cluster(self.cluster)
        net_serializer = serializer.get_net_provider_serializer(self.cluster)
        self.assertIs(net_serializer, NeutronNetworkDeploymentSerializer70)

        nm = objects.Cluster.get_network_manager(self.cluster)
        networks = nm.get_node_networks(compute)
        public_net = next((net for net in networks if net['name'] == 'public'),
                          None)
        self.assertIsNotNone(public_net)

        self.assertFalse(objects.Node.should_have_public_with_ip(compute))
        network_scheme = net_serializer.generate_network_scheme(
            compute, networks)
        expected = {'action': 'add-port',
                    'bridge': 'br-ex',
                    'name': public_net['dev']}
        self.assertIn(expected, network_scheme['transformations'])

    def test_replacements_in_network_assignments(self):

        node_roles_vs_net_names = [
            (['controller'], ['public', 'management', 'fuelweb_admin']),
            (['compute', 'cinder'],
             ['storage', 'management', 'fuelweb_admin'])]

        template_meta = self.net_template["adv_net_template"]["default"]

        iface_var = template_meta['nic_mapping']['default'].keys()[0]

        ep_with_var = "<% {0} %>.123".format(iface_var)

        template_meta['network_assignments']['storage']['ep'] = ep_with_var
        template_meta['network_scheme']['storage']['endpoints'] = \
            [ep_with_var]

        objects.Cluster.set_network_template(
            self.cluster,
            self.net_template
        )
        cluster_db = objects.Cluster.get_by_uid(self.cluster['id'])
        objects.Cluster.prepare_for_deployment(cluster_db)

        serializer = get_serializer_for_cluster(self.cluster)
        serialized_for_astute = serializer(
            AstuteGraph(cluster_db)).serialize(self.cluster, cluster_db.nodes)

        for node_data in serialized_for_astute:
            node = objects.Node.get_by_uid(node_data['uid'])
            for node_roles, net_names in node_roles_vs_net_names:
                if node.all_roles == set(node_roles):
                    self.check_node_ips_on_certain_networks(node, net_names)
                    break
            else:
                self.fail("Unexpected combination of node roles: {0}".format(
                    node.all_roles))

    def test_multiple_node_roles_network_roles(self):
        expected_roles = {
            # controller node
            objects.Node.get_node_fqdn(self.cluster.nodes[0]): {
                'management': 'br-mgmt',
                'admin/pxe': 'br-fw-admin',
                'swift/api': 'br-mgmt',
                'neutron/api': 'br-mgmt',
                'sahara/api': 'br-mgmt',
                'aodh/api': 'br-mgmt',
                'ceilometer/api': 'br-mgmt',
                'cinder/api': 'br-mgmt',
                'keystone/api': 'br-mgmt',
                'glance/api': 'br-mgmt',
                'heat/api': 'br-mgmt',
                'nova/api': 'br-mgmt',
                'murano/api': 'br-mgmt',
                'horizon': 'br-mgmt',
                'mgmt/memcache': 'br-mgmt',
                'mgmt/database': 'br-mgmt',
                'ceph/public': 'br-mgmt',
                'public/vip': 'br-ex',
                'swift/public': 'br-ex',
                'neutron/floating': 'br-floating',
                'ceph/radosgw': 'br-ex',
                'mgmt/messaging': 'br-mgmt',
                'neutron/mesh': 'br-mgmt',
                'mgmt/vip': 'br-mgmt',
                'mgmt/corosync': 'br-mgmt',
                'mongo/db': 'br-mgmt',
                'nova/migration': 'br-mgmt',
                'fw-admin': 'br-fw-admin',
                'ex': 'br-ex'
            },
            # compute/cinder node
            objects.Node.get_node_fqdn(self.cluster.nodes[1]): {
                'management': 'br-mgmt',
                'admin/pxe': 'br-fw-admin',
                'swift/api': 'br-mgmt',
                'neutron/api': 'br-mgmt',
                'sahara/api': 'br-mgmt',
                'aodh/api': 'br-mgmt',
                'ceilometer/api': 'br-mgmt',
                'cinder/api': 'br-mgmt',
                'keystone/api': 'br-mgmt',
                'glance/api': 'br-mgmt',
                'heat/api': 'br-mgmt',
                'nova/api': 'br-mgmt',
                'murano/api': 'br-mgmt',
                'horizon': 'br-mgmt',
                'mgmt/memcache': 'br-mgmt',
                'mgmt/database': 'br-mgmt',
                'ceph/public': 'br-mgmt',
                'cinder/iscsi': 'br-storage',
                'swift/replication': 'br-storage',
                'ceph/replication': 'br-storage',
                'neutron/private': 'br-prv',
                'mgmt/messaging': 'br-mgmt',
                'neutron/mesh': 'br-mgmt',
                'mgmt/vip': 'br-mgmt',
                'mgmt/corosync': 'br-mgmt',
                'mongo/db': 'br-mgmt',
                'nova/migration': 'br-mgmt',
                'fw-admin': 'br-fw-admin',
                'storage': 'br-storage'
            }
        }

        for node in self.serialized_for_astute:
            roles = node['network_scheme']['roles']
            self.assertEqual(roles, expected_roles[node['fqdn']])

    def test_multiple_node_roles_transformations(self):
        node = self.cluster.nodes[1]

        serializer = get_serializer_for_cluster(self.cluster)
        net_serializer = serializer.get_net_provider_serializer(self.cluster)

        transformations = net_serializer.generate_transformations(node)

        # Two node roles with the same template should only generate one
        # transformation.
        admin_brs = filter(lambda t: t.get('name') == 'br-fw-admin',
                           transformations)
        self.assertEqual(1, len(admin_brs))

        # Templates are applied in the order as defined in the template.
        # storage network template is applied after the 4 transformations
        # in common
        self.assertEqual('br-storage', transformations[4]['name'])

        # Ensure all ports connected to br-mgmt happen after the bridge
        # has been created
        port_seen = False
        for tx in transformations:
            if tx.get('name') == 'br-mgmt' and tx['action'] == 'add-br' \
                    and port_seen:
                self.fail('Port was added to br-mgmt prior to the bridge '
                          'being created')
            if tx.get('bridge') == 'br-mgmt' and tx['action'] == 'add-port':
                port_seen = True

    def test_multiple_node_roles_network_metadata(self):
        nm = objects.Cluster.get_network_manager(self.env.clusters[0])
        ip_by_net = {}
        for node_data in self.serialized_for_astute:
            self.assertItemsEqual(
                node_data['network_metadata'], ['nodes', 'vips'])
            nodes = node_data['network_metadata']['nodes']
            for node_name, node_attrs in nodes.items():
                self.assertItemsEqual(
                    node_attrs,
                    ['uid', 'fqdn', 'name', 'user_node_name',
                     'swift_zone', 'node_roles', 'network_roles']
                )
                node = objects.Node.get_by_uid(node_attrs['uid'])
                networks = nm.get_node_networks(node)
                node_nets = [n['name'] for n in networks]

                for net in node_nets:
                    netgroup = nm.get_network_by_netname(net, networks)
                    if netgroup.get('ip'):
                        ip_by_net[net] = netgroup['ip'].split('/')[0]
                self.assertEqual(objects.Node.get_slave_name(node), node_name)
                self.assertEqual(node_attrs['uid'], node.uid)
                self.assertEqual(node_attrs['fqdn'],
                                 objects.Node.get_node_fqdn(node))
                self.assertEqual(node_attrs['name'], node_name)
                self.assertEqual(node_attrs['user_node_name'], node.name)
                self.assertEqual(node_attrs['swift_zone'], node.uid)
                network_roles = {
                    'management': ip_by_net['management'],
                    'admin/pxe': ip_by_net['fuelweb_admin'],
                    'swift/api': ip_by_net['management'],
                    'neutron/api': ip_by_net['management'],
                    'sahara/api': ip_by_net['management'],
                    'aodh/api': ip_by_net['management'],
                    'ceilometer/api': ip_by_net['management'],
                    'cinder/api': ip_by_net['management'],
                    'keystone/api': ip_by_net['management'],
                    'glance/api': ip_by_net['management'],
                    'heat/api': ip_by_net['management'],
                    'nova/api': ip_by_net['management'],
                    'murano/api': ip_by_net['management'],
                    'horizon': ip_by_net['management'],
                    'mgmt/memcache': ip_by_net['management'],
                    'mgmt/database': ip_by_net['management'],
                    'mgmt/messaging': ip_by_net['management'],
                    'neutron/mesh': ip_by_net['management'],
                    'mgmt/vip': ip_by_net['management'],
                    'mgmt/corosync': ip_by_net['management'],
                    'mongo/db': ip_by_net['management'],
                    'nova/migration': ip_by_net['management'],
                    'ceph/public': ip_by_net['management'],
                    'fw-admin': ip_by_net['fuelweb_admin']
                }

                if node.all_roles == set(['controller']):
                    network_roles.update({
                        'public/vip': ip_by_net['public'],
                        'swift/public': ip_by_net['public'],
                        'neutron/floating': None,
                        'ceph/radosgw': ip_by_net['public'],
                        'ex': ip_by_net['public']
                    })
                else:
                    network_roles.update({
                        'cinder/iscsi': ip_by_net['storage'],
                        'swift/replication': ip_by_net['storage'],
                        'ceph/replication': ip_by_net['storage'],
                        'storage': ip_by_net['storage'],
                        'neutron/private': None
                    })
                self.assertEqual(
                    node_attrs['network_roles'],
                    network_roles
                )

    def test_delete_default_network_group(self):
        net_name = "storage"
        node_group = objects.Cluster.get_default_group(self.cluster)
        # delete one of default network group
        storage_net = objects.NetworkGroup.get_from_node_group_by_name(
            node_group.id, net_name)
        objects.NetworkGroup.delete(storage_net)
        # download default template and fix it
        net_template = self.env.read_fixtures(['network_template_70'])[0]
        template_meta = net_template["adv_net_template"]["default"]
        # wipe out network from template
        del(template_meta["network_assignments"][net_name])
        for k, v in template_meta["templates_for_node_role"].iteritems():
            if net_name in v:
                v.remove(net_name)
        del(template_meta["network_scheme"][net_name])
        # apply updated template to the cluster
        objects.Cluster.set_network_template(
            self.cluster,
            net_template
        )
        serializer = get_serializer_for_cluster(self.cluster)
        net_serializer = serializer.get_net_provider_serializer(self.cluster)
        # serializer should not fail if we delete one of default network
        # what is not used in template
        net_serializer.generate_network_metadata(self.cluster)

    def test_network_not_mapped_to_nics_w_template(self):
        # delete and restore management network to break the default
        # networks to interfaces mapping
        resp = self.app.get(
            reverse('NetworkGroupCollectionHandler',
                    kwargs=self.env.clusters[0]),
            headers=self.default_headers,
            expect_errors=False
        )
        management = None
        for ng in jsonutils.loads(resp.body):
            if ng['name'] == 'management':
                management = ng
                break
        self.app.delete(
            reverse(
                'NetworkGroupHandler',
                kwargs={'obj_id': management.pop('id')}
            ),
            headers=self.default_headers
        )
        self.app.post(
            reverse('NetworkGroupCollectionHandler'),
            jsonutils.dumps(management),
            headers=self.default_headers,
            expect_errors=False,
        )
        resp = self.app.get(
            reverse('NetworkGroupCollectionHandler',
                    kwargs=self.env.clusters[0]),
            headers=self.default_headers,
            expect_errors=False
        )
        # management network is not mapped to any interfaces in DB now
        cluster_db = self.db.query(models.Cluster).get(self.cluster['id'])
        objects.Cluster.prepare_for_deployment(cluster_db)
        serializer = get_serializer_for_cluster(cluster_db)
        self.serialized_for_astute = serializer(
            AstuteGraph(cluster_db)).serialize(cluster_db, cluster_db.nodes)

        network_roles = [
            'management',
            'swift/api',
            'neutron/api',
            'sahara/api',
            'aodh/api',
            'ceilometer/api',
            'cinder/api',
            'keystone/api',
            'glance/api',
            'heat/api',
            'nova/api',
            'murano/api',
            'horizon',
            'mgmt/memcache',
            'mgmt/database',
            'mgmt/messaging',
            'neutron/mesh',
            'mgmt/vip',
            'mgmt/corosync',
            'mongo/db',
            'nova/migration'
        ]
        for node_data in self.serialized_for_astute:
            for n in node_data['nodes']:
                n_db = objects.Node.get_by_uid(n['uid'])
                if 'controller' in n_db.roles:
                    self.assertIn('internal_address', n)
                    self.assertIn('internal_netmask', n)
                    self.assertIn('public_address', n)
                    self.assertIn('public_netmask', n)
                    self.assertNotIn('storage_address', n)
                    self.assertNotIn('storage_netmask', n)
                else:
                    self.assertIn('internal_address', n)
                    self.assertIn('internal_netmask', n)
                    self.assertNotIn('public_address', n)
                    self.assertNotIn('public_netmask', n)
                    self.assertIn('storage_address', n)
                    self.assertIn('storage_netmask', n)
            nodes = node_data['network_metadata']['nodes']
            for node_name, node_attrs in nodes.items():
                # IPs must be serialized for these roles which are tied to
                # management network
                for role in network_roles:
                    self.assertIsNotNone(node_attrs['network_roles'][role])

    def test_floating_role_belongs_to_public_bridge(self):
        # download default template and assign floating role to public bridge
        net_template = self.env.read_fixtures(['network_template_70'])[0]
        schemes = net_template["adv_net_template"]["default"]["network_scheme"]
        schemes["public"]["roles"]["neutron/floating"] = "br-ex"
        # apply updated template to the cluster
        objects.Cluster.set_network_template(
            self.cluster,
            net_template
        )
        cluster_db = self.db.query(models.Cluster).get(self.cluster['id'])
        nm = objects.Cluster.get_network_manager(self.env.clusters[0])
        serializer = get_serializer_for_cluster(self.cluster)
        self.serialized_for_astute = serializer(
            AstuteGraph(cluster_db)).serialize(self.cluster, cluster_db.nodes)
        for node_data in self.serialized_for_astute:
            node = objects.Node.get_by_uid(node_data['uid'])
            # check nodes with assigned public ip
            if objects.Node.should_have_public_with_ip(node):
                nets = nm.get_node_networks(node)
                ng = nm.get_network_by_netname('public', nets)
                endpoints = node_data["network_scheme"]["endpoints"]
                self.assertEqual(endpoints["br-ex"]["IP"], [ng.get('ip')])

    def test_get_node_network_mapping(self):
        self.create_more_nodes()
        nm = objects.Cluster.get_network_manager(self.cluster)

        # according to the template different node roles have different sets of
        # networks (endpoints and network names here)
        node_roles_vs_networks = [
            (['controller'], [('public', 'br-ex'),
                              ('management', 'br-mgmt'),
                              ('fuelweb_admin', 'br-fw-admin')]),
            (['compute'], [('private', 'br-prv'),
                           ('storage', 'br-storage'),
                           ('management', 'br-mgmt'),
                           ('fuelweb_admin', 'br-fw-admin')]),
            (['cinder'], [('storage', 'br-storage'),
                          ('management', 'br-mgmt'),
                          ('fuelweb_admin', 'br-fw-admin')]),
            (['compute', 'cinder'], [('private', 'br-prv'),
                                     ('storage', 'br-storage'),
                                     ('management', 'br-mgmt'),
                                     ('fuelweb_admin', 'br-fw-admin')]),
            (['controller', 'cinder'], [('public', 'br-ex'),
                                        ('storage', 'br-storage'),
                                        ('management', 'br-mgmt'),
                                        ('fuelweb_admin', 'br-fw-admin')])]

        for node in self.env.nodes:
            net_names_and_eps = nm.get_node_network_mapping(node)
            for node_roles, networks in node_roles_vs_networks:
                if node.all_roles == set(node_roles):
                    self.assertItemsEqual(net_names_and_eps, networks)

    def test_get_network_name_to_endpoint_mappings(self):
        nm = objects.Cluster.get_network_manager(self.cluster)
        group_id = objects.Cluster.get_default_group(self.cluster).id
        self.assertEqual(
            nm.get_network_name_to_endpoint_mappings(self.cluster),
            {
                group_id: {
                    'br-ex': 'public',
                    'br-mgmt': 'management',
                    'br-fw-admin': 'fuelweb_admin',
                    'br-prv': 'private',
                    'br-storage': 'storage',
                }
            }
        )

    def test_assign_ips_in_node_group(self):
        mgmt = self.db.query(models.NetworkGroup).\
            filter_by(name='management').first()
        ips_2_db = self.db.query(models.IPAddr.ip_addr).\
            filter(models.IPAddr.network == mgmt.id,
                   models.IPAddr.node.isnot(None))
        # two nodes now
        self.assertEqual(ips_2_db.count(), 2)
        ips_2_str = set(ips_2_db)

        # add three nodes
        self.create_more_nodes()
        node_ids = set(n.id for n in self.env.nodes)
        ip_ranges = [netaddr.IPRange(r.first, r.last)
                     for r in mgmt.ip_ranges]
        nm = objects.Cluster.get_network_manager(self.cluster)
        nm.assign_ips_in_node_group(
            mgmt.id, mgmt.name, node_ids, ip_ranges)

        ips_5_db = self.db.query(models.IPAddr.ip_addr). \
            filter(models.IPAddr.network == mgmt.id,
                   models.IPAddr.node.isnot(None))
        self.assertEqual(ips_5_db.count(), 5)
        ips_5_str = set(ips_5_db)
        # old IPs are the same
        self.assertEqual(len(ips_5_str.difference(ips_2_str)), 3)


class TestCustomNetGroupIpAllocation(BaseDeploymentSerializer):

    env_version = '2015.1.0-7.0'

    def setUp(self):
        super(TestCustomNetGroupIpAllocation, self).setUp()
        self.cluster = self.create_env()
        self.cluster_db = self.env.clusters[-1]

    def create_env(self):
        return self.env.create(
            release_kwargs={'version': self.env_version},
            cluster_kwargs={
                'api': False,
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': consts.NEUTRON_SEGMENT_TYPES.gre},
            nodes_kwargs=[
                {'roles': ['controller']},
                {'roles': ['compute']},
            ])

    def test_ip_allocation(self):
        self.env._create_network_group(
            cluster=self.cluster, name='test', cidr='172.16.122.0/24',
            meta={'notation': 'ip_ranges',
                  'ip_range': ['172.16.122.2', '172.16.122.255']})
        objects.Cluster.prepare_for_deployment(self.cluster_db)

        ip_column_name = models.IPAddr.ip_addr.label('ip')
        ip_addrs_count = db().query(models.IPAddr).filter(
            "inet '172.16.122/24' >> {0}".format(ip_column_name)
        ).count()

        self.assertEqual(ip_addrs_count, 2)


class TestSerializer70Mixin(object):

    env_version = "2015.1.0-7.0"


class TestNovaOrchestratorSerializer70(TestSerializer70Mixin,
                                       TestNovaOrchestratorSerializer,
                                       PrepareDataMixin):

    def create_env(self, mode, network_manager='FlatDHCPManager'):
        node_args = [
            {'roles': ['controller', 'cinder'], 'pending_addition': True},
            {'roles': ['compute', 'cinder'], 'pending_addition': True},
            {'roles': ['compute'], 'pending_addition': True},
            {'roles': ['mongo'], 'pending_addition': True},
            {'roles': [], 'pending_roles': ['cinder'],
             'pending_addition': True}]

        release = self.patch_net_roles_for_release()
        cluster = self.env.create(
            cluster_kwargs={
                'release_id': release.id,
                'mode': mode,
                'net_manager': network_manager,
                'net_provider': consts.CLUSTER_NET_PROVIDERS.nova_network},
            nodes_kwargs=node_args)

        cluster_db = self.db.query(models.Cluster).get(cluster['id'])
        objects.Cluster.prepare_for_deployment(cluster_db)
        self.db.flush()
        return cluster_db


class TestSerializeInterfaceDriversData70(TestSerializer70Mixin,
                                          TestSerializeInterfaceDriversData):
    pass


class TestDeploymentHASerializer70(TestSerializer70Mixin,
                                   TestDeploymentHASerializer61):
    pass
