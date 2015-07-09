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

import mock
import six
import yaml

from nailgun.db.sqlalchemy import models
from nailgun.network.manager import NetworkManager
from nailgun import objects
from nailgun.orchestrator.deployment_graph import AstuteGraph
from nailgun.orchestrator.deployment_serializers import \
    get_serializer_for_cluster
from nailgun.test.integration.test_orchestrator_serializer import \
    BaseDeploymentSerializer


class TestDeploymentAttributesSerialization70(BaseDeploymentSerializer):
    @mock.patch.object(models.Release, 'environment_version',
                       new_callable=mock.PropertyMock(return_value='7.0'))
    def setUp(self, *args):
        super(TestDeploymentAttributesSerialization70, self).setUp()
        self.cluster = self.create_env('ha_compact')

        # NOTE: 'prepare_for_deployment' is going to be changed for 7.0
        objects.NodeCollection.prepare_for_deployment(self.env.nodes, 'vlan')
        cluster_db = self.db.query(models.Cluster).get(self.cluster['id'])
        serializer = get_serializer_for_cluster(cluster_db)
        self.serialized_for_astute = serializer(
            AstuteGraph(cluster_db)).serialize(cluster_db, cluster_db.nodes)

    def create_env(self, mode):
        return self.env.create(
            cluster_kwargs={
                'mode': mode,
                'net_provider': 'neutron',
                'net_segment_type': 'vlan'},
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
                'neutron/api': 'br-mgmt',
                'swift/api': 'br-mgmt',
                'sahara/api': 'br-mgmt',
                'ceilometer/api': 'br-mgmt',
                'cinder/api': 'br-mgmt',
                'glance/api': 'br-mgmt',
                'heat/api': 'br-mgmt',
                'nova/api': 'br-mgmt',
                'murano/api': 'br-mgmt',
                'horizon': 'br-mgmt',

                'mgmt/api': 'br-mgmt',
                'mgmt/database': 'br-mgmt',
                'mgmt/messaging': 'br-mgmt',
                'mgmt/corosync': 'br-mgmt',
                'mgmt/memcache': 'br-mgmt',
                'mgmt/vip': 'br-mgmt',

                'public/vip': 'br-ex',

                'neutron/private': 'br-prv',
                'neutron/mesh': 'br-mgmt',
                'neutron/floating': 'br-floating',

                'swift/replication': 'br-storage',

                'ceph/public': 'br-mgmt',
                'ceph/radosgw': 'br-ex',
                'ceph/replication': 'br-storage',

                'cinder/iscsi': 'br-storage',

                'mongo/db': 'br-mgmt',

                # deprecated
                'fw-admin': 'br-fw-admin',
                'management': 'br-mgmt',
                'ex': 'br-ex',
                'storage': 'br-storage',
            }
            self.assertEqual(roles, expected_roles)

    def test_offloading_modes_serialize(self):
        meta = self.env.default_metadata()
        changed_offloading_modes = {}
        for interface in meta['interfaces']:
            changed_offloading_modes[interface['name']] = \
                NetworkManager._get_modified_offloading_modes(
                    interface.get('offloading_modes')
                )

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
        nm = objects.Cluster.get_network_manager(self.env.clusters[0])
        ip_by_net = {
            'fuelweb_admin': None,
            'storage': None,
            'management': None,
            'public': None
        }
        node = self.env.nodes[0]
        for net in ip_by_net:
            netgroup = nm.get_node_network_by_netname(node, net)
            if netgroup.get('ip'):
                ip_by_net[net] = netgroup['ip'].split('/')[0]
        for node_data in self.serialized_for_astute:
            self.assertItemsEqual(
                node_data['network_metadata'], ['nodes', 'vips'])
            for k, v in six.iteritems(node_data['network_metadata']['nodes']):
                self.assertItemsEqual(
                    v,
                    ['uid', 'fqdn', 'name', 'user_node_name',
                     'swift_zone', 'node_roles', 'network_roles']
                )
                self.assertEqual(objects.Node.make_slave_name(node), k)
                self.assertEqual(v['uid'], node.uid)
                self.assertEqual(v['fqdn'], node.fqdn)
                self.assertEqual(v['name'], k)
                self.assertEqual(v['user_node_name'], node.name)
                self.assertEqual(v['swift_zone'], node.uid)

                network_roles = {
                    'admin/pxe': ip_by_net['fuelweb_admin'],
                    'fw-admin': ip_by_net['fuelweb_admin'],

                    'keystone/api': ip_by_net['management'],
                    'neutron/api': ip_by_net['management'],
                    'swift/api': ip_by_net['management'],
                    'sahara/api': ip_by_net['management'],
                    'ceilometer/api': ip_by_net['management'],
                    'cinder/api': ip_by_net['management'],
                    'glance/api': ip_by_net['management'],
                    'heat/api': ip_by_net['management'],
                    'nova/api': ip_by_net['management'],
                    'murano/api': ip_by_net['management'],
                    'horizon': ip_by_net['management'],

                    'management': ip_by_net['management'],
                    'mgmt/api': ip_by_net['management'],
                    'mgmt/database': ip_by_net['management'],
                    'mgmt/messaging': ip_by_net['management'],
                    'mgmt/corosync': ip_by_net['management'],
                    'mgmt/memcache': ip_by_net['management'],
                    'mgmt/vip': ip_by_net['management'],

                    'mongo/db': ip_by_net['management'],

                    'neutron/mesh': ip_by_net['management'],

                    'ceph/public': ip_by_net['management'],

                    'neutron/private': None,
                    'neutron/floating': None,

                    'storage': ip_by_net['storage'],
                    'ceph/replication': ip_by_net['storage'],
                    'swift/replication': ip_by_net['storage'],
                    'cinder/iscsi': ip_by_net['storage'],

                    'ex': ip_by_net['public'],
                    'public/vip': ip_by_net['public'],
                    'ceph/radosgw': ip_by_net['public'],
                }
                self.assertEqual(
                    v['network_roles'],
                    network_roles
                )


class TestRolesSerializationWithPlugins(BaseDeploymentSerializer):

    ROLES = yaml.load("""
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

    DEPLOYMENT_TASKS = yaml.load("""
        - id: test_role
          type: group
          role: [test_role]
          required_for: [deploy_end]
          requires: [deploy_start]
          parameters:
            strategy:
              type: one_by_one

        - id: do-something
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

        self.env.create(
            release_kwargs={
                'version': '2015.1.0-7.0',
            },
            cluster_kwargs={
                'mode': 'ha_compact',
                'net_provider': 'neutron',
                'net_segment_type': 'vlan',
            })
        self.cluster = self.env.clusters[0]

    def _get_serializer(self, cluster):
        return get_serializer_for_cluster(cluster)(AstuteGraph(cluster))

    def test_tasks_were_serialized(self):
        plugin_data = self.env.get_default_plugin_metadata()
        plugin_data['roles_metadata'] = self.ROLES
        plugin_data['deployment_tasks'] = self.DEPLOYMENT_TASKS
        plugin = objects.Plugin.create(plugin_data)
        self.cluster.plugins.append(plugin)

        self.env.create_node(
            api=True,
            cluster_id=self.cluster.id,
            pending_roles=['test_role'],
            pending_addition=True)
        self.db.flush()

        objects.NodeCollection.prepare_for_deployment(self.cluster.nodes)

        serializer = self._get_serializer(self.cluster)
        serialized_data = serializer.serialize(
            self.cluster, self.cluster.nodes)
        self.assertItemsEqual(serialized_data[0]['tasks'], [{
            'parameters': {
                'cwd': '/',
                'puppet_manifest': '/path/to/manifests',
                'puppet_modules': '/path/to/modules',
                'timeout': 3600,
            },
            'priority': 100,
            'type': 'puppet',
            'uids': [self.cluster.nodes[0].uid],
        }])

    def test_tasks_were_not_serialized(self):
        plugin_data = self.env.get_default_plugin_metadata()
        plugin_data['roles_metadata'] = {}
        plugin_data['deployment_tasks'] = self.DEPLOYMENT_TASKS
        plugin = objects.Plugin.create(plugin_data)
        self.cluster.plugins.append(plugin)

        self.env.create_node(
            api=True,
            cluster_id=self.cluster.id,
            pending_roles=['controller'],
            pending_addition=True)
        self.db.flush()

        objects.NodeCollection.prepare_for_deployment(self.cluster.nodes)

        serializer = self._get_serializer(self.cluster)
        serialized_data = serializer.serialize(
            self.cluster, self.cluster.nodes)
        self.assertItemsEqual(serialized_data[0]['tasks'], [{
            'parameters': {
                'cwd': '/',
                'puppet_manifest': '/etc/puppet/manifests/site.pp',
                'puppet_modules': '/etc/puppet/modules',
                'timeout': 3600,
            },
            'priority': 100,
            'type': 'puppet',
            'uids': [self.cluster.nodes[0].uid],
        }])
