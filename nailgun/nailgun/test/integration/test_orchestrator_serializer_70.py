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

from nailgun import consts
from nailgun.db.sqlalchemy import models
from nailgun.network.manager import NetworkManager
from nailgun import objects
from nailgun.orchestrator import stages
from nailgun.test import base

from nailgun.orchestrator.deployment_graph import AstuteGraph
from nailgun.orchestrator.deployment_serializers import \
    get_serializer_for_cluster
from nailgun.orchestrator.neutron_serializers import \
    NeutronNetworkDeploymentSerializer70
from nailgun.orchestrator.neutron_serializers import \
    NeutronNetworkTemplateSerializer70
from nailgun.test.integration.test_orchestrator_serializer import \
    BaseDeploymentSerializer


class BaseTestDeploymentAttributesSerialization70(BaseDeploymentSerializer):
    management = ['keystone/api', 'neutron/api', 'swift/api', 'sahara/api',
                  'ceilometer/api', 'cinder/api', 'glance/api', 'heat/api',
                  'nova/api', 'murano/api', 'horizon', 'management',
                  'mgmt/api', 'mgmt/database', 'mgmt/messaging',
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

    def setUp(self):
        super(BaseTestDeploymentAttributesSerialization70, self).setUp()
        self.cluster = self.create_env('ha_compact')

        # NOTE: 'prepare_for_deployment' is going to be changed for 7.0
        objects.NodeCollection.prepare_for_deployment(
            self.env.nodes, self.segmentation_type)
        self.cluster_db = self.db.query(models.Cluster).get(self.cluster['id'])
        serializer_type = get_serializer_for_cluster(self.cluster_db)
        self.serializer = serializer_type(AstuteGraph(self.cluster_db))
        self.serialized_for_astute = self.serializer.serialize(
            self.cluster_db, self.cluster_db.nodes)
        self.vm_data = self.env.read_fixtures(['vmware_attributes'])

    def create_env(self, mode):
        return self.env.create(
            release_kwargs={'version': '2015.1.0-7.0'},
            cluster_kwargs={
                'mode': mode,
                'net_provider': 'neutron',
                'net_segment_type': self.segmentation_type},
            nodes_kwargs=[
                {'roles': ['controller'],
                 'pending_addition': True},
                {'roles': ['compute'],
                 'pending_addition': True}])


class TestDeploymentAttributesSerialization70(
    BaseTestDeploymentAttributesSerialization70
):
    segmentation_type = consts.NEUTRON_SEGMENT_TYPES.vlan

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
                self.assertEqual(v['fqdn'], node.fqdn)
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


class TestDeploymentSerializationForNovaNetwork70(BaseDeploymentSerializer):
    @mock.patch.object(models.Release, 'environment_version',
                       new_callable=mock.PropertyMock(return_value='7.0'))
    def setUp(self, *args):
        super(TestDeploymentSerializationForNovaNetwork70, self).setUp()
        self.cluster = self.create_env('ha_compact')

        # NOTE: 'prepare_for_deployment' is going to be changed for 7.0
        objects.NodeCollection.prepare_for_deployment(self.env.nodes)
        cluster_db = self.db.query(models.Cluster).get(self.cluster['id'])
        serializer_type = get_serializer_for_cluster(cluster_db)
        self.serializer = serializer_type(AstuteGraph(cluster_db))
        self.serialized_for_astute = self.serializer.serialize(
            cluster_db, cluster_db.nodes)
        self.vm_data = self.env.read_fixtures(['vmware_attributes'])

    def create_env(self, mode):
        return self.env.create(
            cluster_kwargs={
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
        for net in ip_by_net:
            netgroup = nm.get_node_network_by_netname(node, net)
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
                self.assertEqual(node_attrs['fqdn'], node.fqdn)
                self.assertEqual(node_attrs['name'], node_name)
                self.assertEqual(node_attrs['user_node_name'], node.name)
                self.assertEqual(node_attrs['swift_zone'], node.uid)

                network_roles = {
                    'admin/pxe': ip_by_net['fuelweb_admin'],
                    'fw-admin': ip_by_net['fuelweb_admin'],

                    'keystone/api': ip_by_net['management'],
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

        self.cluster = self._prepare_cluster()

    def _prepare_cluster(self):
        self.env.create(
            release_kwargs={
                'version': '2015.1.0-7.0',
                'deployment_tasks': self.release_deployment_tasks,
            },
            cluster_kwargs={
                'mode': 'ha_compact',
                'net_provider': 'neutron',
                'net_segment_type': consts.NEUTRON_SEGMENT_TYPES.vlan,
            },
            nodes_kwargs=[
                {'roles': ['controller'], 'primary_roles': ['controller'],
                 'pending_addition': True}
            ]
        )
        return self.env.clusters[0]

    def prepare_plugins_for_cluster(self, cluster, plugins_kw_list):
        plugins = [
            self._create_plugin(**kw)
            for kw in plugins_kw_list
        ]
        cluster.plugins.extend(plugins)
        self.db.flush()

    def _create_plugin(self, **plugin_kwargs):
        plugin_kwargs.update(
            {
                'releases': [
                    {
                        'repository_path': 'plugin_test',
                        'version': self.cluster.release.version,
                        'os':
                        self.cluster.release.operating_system.lower(),
                        'mode': ['ha', 'multinode'],
                        'deployment_scripts_path': 'plugin_test/'
                    },
                ],
            }
        )
        plugin_data = self.env.get_default_plugin_metadata(
            **plugin_kwargs
        )

        return objects.Plugin.create(plugin_data)

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
        objects.NodeCollection.prepare_for_deployment(self.cluster.nodes)
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
        objects.NodeCollection.prepare_for_deployment(self.cluster.nodes)
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
        objects.NodeCollection.prepare_for_deployment(self.cluster.nodes)
        with mock.patch('nailgun.plugins.adapters.glob.glob',
                        mock.Mock(return_value='path/to/test/repos')):
            pre_deployment = stages.pre_deployment_serialize(
                graph, self.cluster, self.cluster.nodes)

        for task_type in (consts.ORCHESTRATOR_TASK_TYPES.sync,
                          consts.ORCHESTRATOR_TASK_TYPES.upload_file):
            self._check_pre_deployment_tasks(pre_deployment, task_type)

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
        objects.NodeCollection.prepare_for_deployment(self.cluster.nodes)
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
        objects.NodeCollection.prepare_for_deployment(self.cluster.nodes)
        serializer = \
            get_serializer_for_cluster(self.cluster)(graph)
        serialized = serializer.serialize(self.cluster, self.cluster.nodes)

        tasks = serialized[0]['tasks']
        release_depl_tasks_ids = ('first-fake-depl-task',
                                  'second-fake-depl-task')

        serialized_tasks_ids = (t['parameters']['puppet_manifest']
                                for t in tasks)
        self.assertItemsEqual(release_depl_tasks_ids, serialized_tasks_ids)


class TestRolesSerializationWithPlugins(BaseDeploymentSerializer):

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
                'cwd': '/etc/fuel/plugins/testing_plugin-0.1.0/',
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


class TestNetworkTemplateSerializer70(BaseDeploymentSerializer):

    def setUp(self, *args):
        super(TestNetworkTemplateSerializer70, self).setUp()
        self.cluster = self.create_env('ha_compact')
        self.net_template = self.env.read_fixtures(['network_template'])[0]

        objects.Cluster.set_network_template(
            self.cluster,
            self.net_template
        )
        objects.NodeCollection.prepare_for_deployment(self.env.nodes)
        cluster_db = self.db.query(models.Cluster).get(self.cluster['id'])

        serializer = get_serializer_for_cluster(self.cluster)
        self.serialized_for_astute = serializer(
            AstuteGraph(cluster_db)).serialize(self.cluster, cluster_db.nodes)

    def create_env(self, mode):
        return self.env.create(
            release_kwargs={'version': '11111-7.0'},
            cluster_kwargs={
                'api': False,
                'mode': mode,
                'net_provider': 'neutron',
                'net_segment_type': 'vlan'},
            nodes_kwargs=[
                {'roles': ['controller'],
                 'pending_addition': True,
                 'name': self.node_name},
                {'roles': ['compute', 'cinder'],
                 'pending_addition': True,
                 'name': self.node_name}
            ])

    def test_get_net_provider_serializer(self):
        serializer = get_serializer_for_cluster(self.cluster)
        self.cluster.network_config.configuration_template = None

        net_serializer = serializer.get_net_provider_serializer(self.cluster)
        self.assertIs(net_serializer, NeutronNetworkDeploymentSerializer70)

        self.cluster.network_config.configuration_template = \
            self.net_template
        net_serializer = serializer.get_net_provider_serializer(self.cluster)
        self.assertIs(net_serializer, NeutronNetworkTemplateSerializer70)

    def test_multiple_node_roles_network_roles(self):
        expected_roles = {
            # controller node
            self.cluster.nodes[0].fqdn: {
                'management': 'br-mgmt',
                'admin/pxe': 'br-fw-admin',
                'swift/api': 'br-mgmt',
                'neutron/api': 'br-mgmt',
                'sahara/api': 'br-mgmt',
                'ceilometer/api': 'br-mgmt',
                'cinder/api': 'br-mgmt',
                'keystone/api': 'br-mgmt',
                'glance/api': 'br-mgmt',
                'heat/api': 'br-mgmt',
                'nova/api': 'br-mgmt',
                'murano/api': 'br-mgmt',
                'horizon': 'br-mgmt',
                'mgmt/api': 'br-mgmt',
                'mgmt/memcache': 'br-mgmt',
                'mgmt/database': 'br-mgmt',
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
                'ex': 'br-ex',
                'ceph/public': 'br-ex',
            },
            # compute/cinder node
            self.cluster.nodes[1].fqdn: {
                'management': 'br-mgmt',
                'admin/pxe': 'br-fw-admin',
                'swift/api': 'br-mgmt',
                'neutron/api': 'br-mgmt',
                'sahara/api': 'br-mgmt',
                'ceilometer/api': 'br-mgmt',
                'cinder/api': 'br-mgmt',
                'keystone/api': 'br-mgmt',
                'glance/api': 'br-mgmt',
                'heat/api': 'br-mgmt',
                'nova/api': 'br-mgmt',
                'murano/api': 'br-mgmt',
                'horizon': 'br-mgmt',
                'mgmt/api': 'br-mgmt',
                'mgmt/memcache': 'br-mgmt',
                'mgmt/database': 'br-mgmt',
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
        ip_by_net = {
            'fuelweb_admin': None,
            'storage': None,
            'management': None,
            'public': None
        }
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
                for net in ip_by_net:
                    netgroup = nm.get_node_network_by_netname(node, net)
                    if netgroup.get('ip'):
                        ip_by_net[net] = netgroup['ip'].split('/')[0]
                self.assertEqual(objects.Node.get_slave_name(node), node_name)
                self.assertEqual(node_attrs['uid'], node.uid)
                self.assertEqual(node_attrs['fqdn'], node.fqdn)
                self.assertEqual(node_attrs['name'], node_name)
                self.assertEqual(node_attrs['user_node_name'], node.name)
                self.assertEqual(node_attrs['swift_zone'], node.uid)
                network_roles = {
                    'management': ip_by_net['management'],
                    'admin/pxe': ip_by_net['fuelweb_admin'],
                    'swift/api': ip_by_net['management'],
                    'neutron/api': ip_by_net['management'],
                    'sahara/api': ip_by_net['management'],
                    'ceilometer/api': ip_by_net['management'],
                    'cinder/api': ip_by_net['management'],
                    'keystone/api': ip_by_net['management'],
                    'glance/api': ip_by_net['management'],
                    'heat/api': ip_by_net['management'],
                    'nova/api': ip_by_net['management'],
                    'murano/api': ip_by_net['management'],
                    'horizon': ip_by_net['management'],
                    'mgmt/api': ip_by_net['management'],
                    'mgmt/memcache': ip_by_net['management'],
                    'mgmt/database': ip_by_net['management'],
                    'mgmt/messaging': ip_by_net['management'],
                    'neutron/mesh': ip_by_net['management'],
                    'mgmt/vip': ip_by_net['management'],
                    'mgmt/corosync': ip_by_net['management'],
                    'mongo/db': ip_by_net['management'],
                    'nova/migration': ip_by_net['management'],
                    'fw-admin': ip_by_net['fuelweb_admin']
                }

                if node.all_roles == set(['controller']):
                    network_roles.update({
                        'public/vip': ip_by_net['public'],
                        'swift/public': ip_by_net['public'],
                        'neutron/floating': None,
                        'ceph/radosgw': ip_by_net['public'],
                        'ex': ip_by_net['public'],
                        'ceph/public': ip_by_net['public'],
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
