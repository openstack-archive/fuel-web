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

from copy import deepcopy
from mock import patch
import netaddr

from oslo_serialization import jsonutils

from nailgun import consts
from nailgun import objects

from nailgun.db.sqlalchemy import models
from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun.extensions.network_manager.manager import NetworkManager
from nailgun.objects import Task
from nailgun.settings import settings
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import mock_rpc
from nailgun.utils import reverse


class TestHandlers(BaseIntegrationTest):

    @mock_rpc(pass_mock=True)
    def test_deploy_and_remove_correct_nodes_and_statuses(self, mocked_rpc):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {
                    "pending_addition": True,
                },
                {
                    "status": "error",
                    "pending_deletion": True
                }
            ]
        )
        self.env.launch_deployment()

        # launch_deployment kicks ClusterChangesHandler
        # which in turns launches DeploymentTaskManager
        # which runs DeletionTask, ProvisionTask and DeploymentTask.
        # DeletionTask is sent to one orchestrator worker and
        # ProvisionTask and DeploymentTask messages are sent to
        # another orchestrator worker.
        # That is why we expect here list of two sets of
        # arguments in mocked nailgun.rpc.cast
        # The first set of args is for deletion task and
        # the second one is for provisioning and deployment.

        # remove_nodes method call [0][0][1]
        n_rpc_remove = mocked_rpc.call_args_list[0][0][1]['args']['nodes']
        self.assertEqual(len(n_rpc_remove), 1)
        self.assertEqual(n_rpc_remove[0]['uid'], self.env.nodes[1].id)

        # provision method call [1][0][1][0]
        n_rpc_provision = mocked_rpc.call_args_list[1][0][1][0][
            'args']['provisioning_info']['nodes']
        # Nodes will be appended in provision list if
        # they 'pending_deletion' = False and
        # 'status' in ('discover', 'provisioning') or
        # 'status' = 'error' and 'error_type' = 'provision'
        # So, only one node from our list will be appended to
        # provision list.
        self.assertEqual(len(n_rpc_provision), 1)
        self.assertEqual(
            n_rpc_provision[0]['name'],
            objects.Node.get_slave_name(self.env.nodes[0])
        )

        # deploy method call [1][0][1][1]
        n_rpc_deploy = mocked_rpc.call_args_list[
            1][0][1][1]['args']['deployment_info']
        self.assertEqual(len(n_rpc_deploy), 1)
        self.assertEqual(n_rpc_deploy[0]['uid'], str(self.env.nodes[0].id))

    @mock_rpc(pass_mock=True)
    def test_deploy_multinode_neutron_gre_w_custom_public_ranges(self,
                                                                 mocked_rpc):
        cluster = self.env.create(
            cluster_kwargs={'net_provider': 'neutron',
                            'net_segment_type': 'gre'},
            nodes_kwargs=[{"pending_addition": True},
                          {"pending_addition": True},
                          {"pending_addition": True},
                          {"pending_addition": True},
                          {"pending_addition": True}]
        )

        net_data = self.env.neutron_networks_get(cluster.id).json_body
        pub = filter(lambda ng: ng['name'] == 'public',
                     net_data['networks'])[0]
        pub.update({'ip_ranges': [['172.16.0.10', '172.16.0.13'],
                                  ['172.16.0.20', '172.16.0.22']]})

        resp = self.env.neutron_networks_put(cluster.id, net_data)
        self.assertEqual(resp.status_code, 200)

        self.env.launch_deployment()

        args, kwargs = mocked_rpc.call_args
        self.assertEqual(len(args), 2)
        self.assertEqual(len(args[1]), 2)

        n_rpc_deploy = args[1][1]['args']['deployment_info']
        self.assertEqual(len(n_rpc_deploy), 5)
        pub_ips = ['172.16.0.11', '172.16.0.12', '172.16.0.13',
                   '172.16.0.20', '172.16.0.21', '172.16.0.22']
        for n in n_rpc_deploy:
            self.assertIn('management_vrouter_vip', n)
            self.assertIn('public_vrouter_vip', n)
            used_ips = []
            for n_common_args in n['nodes']:
                self.assertIn(n_common_args['public_address'], pub_ips)
                self.assertNotIn(n_common_args['public_address'], used_ips)
                used_ips.append(n_common_args['public_address'])
                self.assertIn('management_vrouter_vip', n)

    @mock_rpc(pass_mock=True)
    def test_deploy_ha_neutron_gre_w_custom_public_ranges(self, mocked_rpc):
        cluster = self.env.create(
            cluster_kwargs={'mode': consts.CLUSTER_MODES.ha_compact,
                            'net_provider': 'neutron',
                            'net_segment_type': 'gre'},
            nodes_kwargs=[{"pending_addition": True},
                          {"pending_addition": True},
                          {"pending_addition": True},
                          {"pending_addition": True},
                          {"pending_addition": True}]
        )

        net_data = self.env.neutron_networks_get(cluster.id).json_body
        pub = filter(lambda ng: ng['name'] == 'public',
                     net_data['networks'])[0]
        pub.update({'ip_ranges': [['172.16.0.10', '172.16.0.13'],
                                  ['172.16.0.20', '172.16.0.22']]})

        resp = self.env.neutron_networks_put(cluster.id, net_data)
        self.assertEqual(resp.status_code, 200)

        self.env.launch_deployment()

        args, kwargs = mocked_rpc.call_args
        self.assertEqual(len(args), 2)
        self.assertEqual(len(args[1]), 2)

        n_rpc_deploy = args[1][1]['args']['deployment_info']
        self.assertEqual(len(n_rpc_deploy), 5)
        pub_ips = ['172.16.0.11', '172.16.0.12', '172.16.0.13',
                   '172.16.0.20', '172.16.0.21', '172.16.0.22']
        for n in n_rpc_deploy:
            self.assertEqual(n['public_vip'], '172.16.0.10')
            used_ips = []
            for n_common_args in n['nodes']:
                self.assertIn(n_common_args['public_address'], pub_ips)
                self.assertNotIn(n_common_args['public_address'], used_ips)
                used_ips.append(n_common_args['public_address'])

    @mock_rpc(pass_mock=True)
    def test_deploy_neutron_gre_w_changed_public_cidr(self, mocked_rpc):
        cluster = self.env.create(
            cluster_kwargs={'net_provider': 'neutron',
                            'net_segment_type': 'gre'},
            nodes_kwargs=[{"pending_addition": True},
                          {"pending_addition": True}]
        )

        net_data = self.env.neutron_networks_get(cluster.id).json_body
        pub = filter(lambda ng: ng['name'] == 'public',
                     net_data['networks'])[0]
        pub.update({'ip_ranges': [['172.16.10.10', '172.16.10.122']],
                    'cidr': '172.16.10.0/24',
                    'gateway': '172.16.10.1'})
        net_data['networking_parameters']['floating_ranges'] = \
            [['172.16.10.130', '172.16.10.254']]

        resp = self.env.neutron_networks_put(cluster.id, net_data)
        self.assertEqual(resp.status_code, 200)

        self.env.launch_deployment()

        args, kwargs = mocked_rpc.call_args
        self.assertEqual(len(args), 2)
        self.assertEqual(len(args[1]), 2)

        n_rpc_deploy = args[1][1]['args']['deployment_info']
        self.assertEqual(len(n_rpc_deploy), 2)
        pub_ips = ['172.16.10.11', '172.16.10.12', '172.16.10.13']
        for n in n_rpc_deploy:
            for n_common_args in n['nodes']:
                self.assertIn(n_common_args['public_address'], pub_ips)

    @mock_rpc(pass_mock=True)
    def test_deploy_neutron_error_not_enough_ip_addresses(self, mocked_rpc):
        cluster = self.env.create(
            cluster_kwargs={'net_provider': 'neutron',
                            'net_segment_type': 'gre'},
            nodes_kwargs=[{"pending_addition": True},
                          {"pending_addition": True},
                          {"pending_addition": True}]
        )

        net_data = self.env.neutron_networks_get(cluster.id).json_body
        pub = filter(lambda ng: ng['name'] == 'public',
                     net_data['networks'])[0]
        pub.update({'ip_ranges': [['172.16.0.10', '172.16.0.11']]})

        resp = self.env.neutron_networks_put(cluster.id, net_data)
        self.assertEqual(resp.status_code, 200)

        task = self.env.launch_deployment()

        self.assertEqual(task.status, 'error')
        self.assertEqual(
            task.message,
            'Not enough IP addresses. Public network 172.16.0.0/24 must have '
            'at least 3 IP addresses for the current environment.')

    def test_occurs_error_not_enough_ip_addresses(self):
        cluster = self.env.create(
            cluster_kwargs={
                'net_provider': consts.CLUSTER_NET_PROVIDERS.nova_network,
            },
            nodes_kwargs=[
                {'pending_addition': True},
                {'pending_addition': True},
                {'pending_addition': True}])

        public_network = self.db.query(
            NetworkGroup).filter_by(name='public').first()

        net_data = {
            "networks": [{
                'id': public_network.id,
                'cidr': '220.0.1.0/24',
                'gateway': '220.0.1.1',
                'ip_ranges': [[
                    '220.0.1.2',
                    '220.0.1.3']]}]}

        self.app.put(
            reverse(
                'NovaNetworkConfigurationHandler',
                kwargs={'cluster_id': cluster.id}),
            jsonutils.dumps(net_data),
            headers=self.default_headers,
            expect_errors=True)

        task = self.env.launch_deployment()

        self.assertEqual(task.status, 'error')
        self.assertEqual(
            task.message,
            'Not enough IP addresses. Public network 220.0.1.0/24 must have '
            'at least 3 IP addresses for the current environment.')

    def test_occurs_error_not_enough_free_space(self):
        meta = self.env.default_metadata()
        meta['disks'] = [{
            "model": "TOSHIBA MK1002TS",
            "name": "sda",
            "disk": "sda",
            # 8GB
            "size": 8000000}]

        self.env.create(
            nodes_kwargs=[
                {"meta": meta, "pending_addition": True}
            ]
        )
        node_db = self.env.nodes[0]

        task = self.env.launch_deployment()

        self.assertEqual(task.status, 'error')
        self.assertEqual(
            task.message,
            "Node '%s' has insufficient disk space" %
            node_db.human_readable_name)

    def test_occurs_error_not_enough_osds_for_ceph(self):
        cluster = self.env.create(
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True},
                {'roles': ['ceph-osd'], 'pending_addition': True}
            ])

        self.app.patch(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster['id']}),
            params=jsonutils.dumps({
                'editable': {
                    'storage': {
                        'volumes_ceph': {'value': True},
                        'osd_pool_size': {'value': '3'},
                        'volumes_lvm': {'value': False},
                    }
                }
            }),
            headers=self.default_headers)

        task = self.env.launch_deployment()

        self.assertEqual(task.status, 'error')
        self.assertEqual(
            task.message,
            'Number of OSD nodes (1) cannot be less than '
            'the Ceph object replication factor (3). '
            'Please either assign ceph-osd role to more nodes, '
            'or reduce Ceph replication factor in the Settings tab.')

    def test_occurs_error_release_is_unavailable(self):
        cluster = self.env.create(
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True}])

        cluster.release.state = consts.RELEASE_STATES.unavailable

        resp = self.app.put(
            reverse(
                'ClusterChangesHandler',
                kwargs={'cluster_id': cluster.id}),
            headers=self.default_headers,
            expect_errors=True)

        self.assertEqual(resp.status_code, 400)
        self.assertRegexpMatches(resp.body, 'Release .* is unavailable')

    @mock_rpc()
    def test_enough_osds_for_ceph(self):
        cluster = self.env.create(
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True},
                {'roles': ['ceph-osd'], 'pending_addition': True},
            ])

        self.app.patch(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster['id']}),
            params=jsonutils.dumps({
                'editable': {
                    'storage': {
                        'volumes_ceph': {'value': True},
                        'osd_pool_size': {'value': '1'},
                        'volumes_lvm': {'value': False},
                    }
                }
            }),
            headers=self.default_headers)

        task = self.env.launch_deployment()
        self.assertNotEqual(task.status, consts.TASK_STATUSES.error)

    @mock_rpc()
    def test_admin_untagged_intersection(self):
        meta = self.env.default_metadata()
        self.env.set_interfaces_in_meta(meta, [{
            "mac": "00:00:00:00:00:66",
            "max_speed": 1000,
            "name": "eth0",
            "current_speed": 1000
        }, {
            "mac": "00:00:00:00:00:77",
            "max_speed": 1000,
            "name": "eth1",
            "current_speed": None}])

        cluster = self.env.create(
            nodes_kwargs=[
                {
                    'api': True,
                    'roles': ['controller'],
                    'pending_addition': True,
                    'meta': meta,
                    'mac': "00:00:00:00:00:66"
                }
            ]
        )

        resp = self.env.neutron_networks_get(cluster.id)
        nets = resp.json_body
        for net in nets["networks"]:
            if net["name"] in ["management", ]:
                net["vlan_start"] = None
        self.env.neutron_networks_put(cluster.id, nets)

        supertask = self.env.launch_deployment()
        self.assertEqual(supertask.status, consts.TASK_STATUSES.error)

    def test_empty_cluster_deploy_error(self):
        cluster = self.env.create(nodes_kwargs=[])
        resp = self.app.put(
            reverse(
                'ClusterChangesHandler',
                kwargs={'cluster_id': cluster.id}
            ),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.db.query(models.Task).count(), 0)

    @mock_rpc()
    def test_deploy_task_status(self):
        self.env.create(
            nodes_kwargs=[{'name': '', 'pending_addition': True}]
        )
        deploy_task = self.env.launch_deployment()
        self.assertEqual(consts.TASK_STATUSES.pending, deploy_task.status)

    @mock_rpc()
    def test_deploymend_possible_without_controllers(self):
        cluster = self.env.create_cluster(api=True)
        self.env.create_node(
            cluster_id=cluster["id"],
            status=consts.NODE_STATUSES.discover,
            pending_roles=["compute"]
        )

        supertask = self.env.launch_deployment()
        self.assertNotEqual(supertask.status, consts.TASK_STATUSES.error)

    @patch('nailgun.task.manager.rpc.cast')
    def test_force_redeploy_changes(self, mcast):
        self.env.create(
            nodes_kwargs=[
                {'status': consts.NODE_STATUSES.ready},
                {'status': consts.NODE_STATUSES.ready},
            ],
            cluster_kwargs={
                'status': consts.CLUSTER_STATUSES.operational
            },
        )

        def _send_request(handler):
            return self.app.put(
                reverse(
                    handler,
                    kwargs={'cluster_id': self.env.clusters[0].id}
                ),
                headers=self.default_headers,
                expect_errors=True
            )

        # Trying to redeploy on cluster in the operational state
        resp = _send_request('ClusterChangesHandler')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json_body.get('message'), 'No changes to deploy')

        # Trying to force redeploy on cluster in the operational state
        resp = _send_request('ClusterChangesForceRedeployHandler')
        self.assertEqual(resp.status_code, 202)

        # Test task is created
        self.assertEqual(resp.json_body.get('name'),
                         consts.TASK_NAMES.deploy)
        self.assertEqual(resp.json_body.get('status'),
                         consts.TASK_STATUSES.pending)

        # Test message is sent
        args, _ = mcast.call_args_list[0]
        deployment_info = args[1][0]['args']['deployment_info']

        self.assertItemsEqual(
            [node.uid for node in self.env.nodes],
            [node['uid'] for node in deployment_info]
        )

    def _test_run(self, mcast, mode='dry_run'):
        self.env.create(
            release_kwargs={
                'operating_system': consts.RELEASE_OS.ubuntu,
                'version': 'mitaka-9.0',
            },
            nodes_kwargs=[
                {
                    'roles': ['controller'],
                    'status': consts.NODE_STATUSES.provisioned
                }
            ],
            cluster_kwargs={
                'status': consts.CLUSTER_STATUSES.operational
            },
        )
        for handler in ('ClusterChangesHandler',
                        'ClusterChangesForceRedeployHandler'):
            resp = self.app.put(
                reverse(
                    handler,
                    kwargs={'cluster_id': self.env.clusters[0].id}
                ) + '?%s=1' % mode,
                headers=self.default_headers,
                expect_errors=True
            )
            self.assertEqual(resp.status_code, 202)
            self.assertEqual(
                mcast.call_args[0][1][0]['args'][mode], True
            )

            task = Task.get_by_uid(
                resp.json_body['id'], fail_if_not_found=True
            )
            self.assertNotEqual(consts.TASK_STATUSES.error, task.status)
            self.assertTrue(task.dry_run)
            Task.delete(task)

    @patch('nailgun.task.manager.rpc.cast')
    def test_dry_run(self, mcast):
        self._test_run(mcast, mode='dry_run')

    @patch('nailgun.task.manager.rpc.cast')
    def test_noop_run(self, mcast):
        self._test_run(mcast, mode='noop_run')

    @patch('nailgun.rpc.cast')
    def test_occurs_error_not_enough_memory_for_hugepages(self, *_):
        meta = self.env.default_metadata()
        meta['numa_topology']['numa_nodes'] = [
            {'cpus': [0, 1, 2], 'id': 0, 'memory': 1024 ** 3}
        ]

        self.env.create(
            release_kwargs={
                'operating_system': consts.RELEASE_OS.ubuntu,
                'version': 'liberty-9.0',
            },
            nodes_kwargs=[
                {'roles': ['compute'], 'pending_addition': True, 'meta': meta},
            ]
        )

        node = self.env.nodes[0]
        node.attributes['hugepages'] = {
            'dpdk': {'type': 'number', 'value': 1026},
            'nova': {'type': 'custom_hugepages', 'value': {'2048': 1}}
        }

        self.db.flush()
        supertask = self.env.launch_deployment()
        self.assertEqual(supertask.status, consts.TASK_STATUSES.error)
        self.assertRegexpMatches(
            supertask.message,
            r'Components .* could not require more memory than node has')

    @patch('nailgun.task.task.DeploymentTask.granular_deploy')
    @patch('nailgun.orchestrator.deployment_serializers.serialize')
    def test_fallback_to_granular(self, mock_serialize, mock_granular_deploy):
        tasks = [
            {'id': 'first-fake-depl-task',
             'type': 'puppet',
             'parameters': {'puppet_manifest': 'first-fake-depl-task',
                            'puppet_modules': 'test',
                            'timeout': 0}}
        ]

        self.env.create(
            release_kwargs={'deployment_tasks': tasks},
            nodes_kwargs=[{'pending_roles': ['controller']}])

        mock_granular_deploy.return_value = 'granular_deploy', {
            'deployment_info': {},
            'pre_deployment': {},
            'post_deployment': {}
        }
        mock_serialize.return_value = {}
        self.env.launch_deployment()

        self.assertEqual(mock_granular_deploy.call_count, 1)
        # Check we didn't serialize cluster in task_deploy
        self.assertEqual(mock_serialize.call_count, 0)
