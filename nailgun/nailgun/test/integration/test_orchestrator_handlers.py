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

from mock import patch
from oslo.serialization import jsonutils

import nailgun

from nailgun import consts
from nailgun import objects

from nailgun.db.sqlalchemy.models import Cluster
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks
from nailgun.test.base import reverse


def make_orchestrator_uri(node_ids):
    return '?nodes={0}'.format(','.join(node_ids))


class TestDefaultOrchestratorInfoHandlers(BaseIntegrationTest):

    def setUp(self):
        super(TestDefaultOrchestratorInfoHandlers, self).setUp()

        cluster = self.env.create(
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True},
                {'roles': ['compute'], 'pending_addition': True},
                {'roles': ['cinder'], 'pending_addition': True}])

        self.cluster = self.db.query(Cluster).get(cluster['id'])

    def customization_handler_helper(self, handler_name, get_info, facts):
        resp = self.app.put(
            reverse(handler_name,
                    kwargs={'cluster_id': self.cluster.id}),
            jsonutils.dumps(facts),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(self.cluster.is_customized)
        self.datadiff(get_info(), facts)

    def test_default_deployment_handler(self):
        resp = self.app.get(
            reverse('DefaultDeploymentInfo',
                    kwargs={'cluster_id': self.cluster.id}),
            headers=self.default_headers)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(3, len(resp.json_body))

    def test_default_provisioning_handler(self):
        resp = self.app.get(
            reverse('DefaultProvisioningInfo',
                    kwargs={'cluster_id': self.cluster.id}),
            headers=self.default_headers)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(3, len(resp.json_body['nodes']))

    def test_default_provisioning_handler_for_selected_nodes(self):
        node_ids = [node.uid for node in self.cluster.nodes][:2]
        url = reverse(
            'DefaultProvisioningInfo',
            kwargs={'cluster_id': self.cluster.id}) + \
            make_orchestrator_uri(node_ids)
        resp = self.app.get(url, headers=self.default_headers)

        self.assertEqual(resp.status_code, 200)
        data = resp.json_body['nodes']
        self.assertEqual(2, len(data))
        actual_uids = [node['uid'] for node in data]
        self.assertItemsEqual(actual_uids, node_ids)

    def test_default_deployment_handler_for_selected_nodes(self):
        node_ids = [node.uid for node in self.cluster.nodes][:2]
        url = reverse(
            'DefaultDeploymentInfo',
            kwargs={'cluster_id': self.cluster.id}) + \
            make_orchestrator_uri(node_ids)
        resp = self.app.get(url, headers=self.default_headers)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(2, len(resp.json_body))
        actual_uids = [node['uid'] for node in resp.json_body]
        self.assertItemsEqual(actual_uids, node_ids)

    def test_cluster_provisioning_customization(self):
        facts = {'engine': {'1': '2'}}
        nodes = []
        for node in self.env.nodes:
            nodes.append({"key": "value", "uid": node.uid})
        facts['nodes'] = nodes
        self.customization_handler_helper(
            'ProvisioningInfo',
            lambda: objects.Cluster.get_provisioning_info(self.cluster),
            facts
        )

    def test_cluster_deployment_customization(self):
        facts = []
        for node in self.env.nodes:
            facts.append({"key": "value", "uid": node.uid})
        self.customization_handler_helper(
            'DeploymentInfo',
            lambda: objects.Cluster.get_deployment_info(self.cluster),
            facts
        )

    def test_deployment_with_one_compute_node(self):
        cluster = self.env.create(
            nodes_kwargs=[
                {'roles': ['compute']}
            ]
        )

        response = self.app.get(
            reverse('DefaultDeploymentInfo',
                    kwargs={'cluster_id': cluster['id']}),
            headers=self.default_headers
        )
        self.assertEqual(response.status_code, 200)


class BaseSelectedNodesTest(BaseIntegrationTest):

    def setUp(self):
        super(BaseSelectedNodesTest, self).setUp()
        self.env.create(
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True},
                {'roles': ['controller'], 'pending_addition': True},
                {'roles': ['controller'], 'pending_addition': True},
                {'roles': ['cinder'], 'pending_addition': True},
                {'roles': ['compute'], 'pending_addition': True},
                {'roles': ['mongo'], 'pending_addition': True},
                {'roles': ['mongo'], 'pending_addition': True},
                {'roles': ['cinder'], 'pending_addition': True}])

        self.cluster = self.env.clusters[0]
        self.node_uids = [n.uid for n in self.cluster.nodes][:3]

    def send_put(self, url, data=None):
        return self.app.put(
            url, jsonutils.dumps(data),
            headers=self.default_headers, expect_errors=True)


class TestSelectedNodesAction(BaseSelectedNodesTest):

    @fake_tasks(fake_rpc=False, mock_rpc=False)
    @patch('nailgun.rpc.cast')
    def test_start_provisioning_on_selected_nodes(self, mock_rpc):
        action_url = reverse(
            'ProvisionSelectedNodes',
            kwargs={'cluster_id': self.cluster.id}) + \
            make_orchestrator_uri(self.node_uids)

        self.send_put(action_url)

        args, kwargs = nailgun.task.manager.rpc.cast.call_args
        provisioned_uids = [
            n['uid'] for n in args[1]['args']['provisioning_info']['nodes']]

        self.assertEqual(3, len(provisioned_uids))
        self.assertItemsEqual(self.node_uids, provisioned_uids)

    def test_start_provisioning_is_unavailable(self):
        action_url = reverse(
            'ProvisionSelectedNodes',
            kwargs={'cluster_id': self.cluster.id}) + \
            make_orchestrator_uri(self.node_uids)
        self.env.releases[0].state = consts.RELEASE_STATES.unavailable

        resp = self.send_put(action_url)

        self.assertEqual(resp.status_code, 400)
        self.assertRegexpMatches(resp.body, 'Release .* is unavailable')

    @fake_tasks(fake_rpc=False, mock_rpc=False)
    @patch('nailgun.rpc.cast')
    def test_start_deployment_on_selected_nodes(self, mock_rpc):
        # if cluster is ha, then DeploySelectedNodes must call
        # TaskHelper.nodes_to_deploy_ha(cluster, nodes) and it must
        # append third controller to the list of nodes which are to deploy
        node_uids = [n.uid for n in self.cluster.nodes][2:3]
        action_url = reverse(
            'DeploySelectedNodes',
            kwargs={'cluster_id': self.cluster.id}) + \
            make_orchestrator_uri(node_uids)

        self.send_put(action_url)

        args, kwargs = nailgun.task.manager.rpc.cast.call_args
        deployed_uids = [n['uid'] for n in args[1]['args']['deployment_info']]
        self.assertEqual(3, len(deployed_uids))
        self.assertItemsEqual(self.node_uids, deployed_uids)


class TestDeploymentHandlerSkipTasks(BaseSelectedNodesTest):

    def setUp(self):
        super(TestDeploymentHandlerSkipTasks, self).setUp()
        self.tasks = ['deploy_legacy']
        self.non_existent = ['non_existent']

    @patch('nailgun.task.task.rpc.cast')
    def test_use_only_certain_tasks(self, mcast):
        action_url = reverse(
            'DeploySelectedNodesWithTasks',
            kwargs={'cluster_id': self.cluster.id}) + \
            make_orchestrator_uri(self.node_uids)
        out = self.send_put(action_url, self.tasks)
        self.assertEqual(out.status_code, 202)
        args, kwargs = mcast.call_args
        deployed_uids = [n['uid'] for n in args[1]['args']['deployment_info']]
        deployment_data = args[1]['args']['deployment_info'][0]
        self.assertEqual(deployed_uids, self.node_uids)
        self.assertEqual(len(deployment_data['tasks']), 1)

    def test_error_raised_on_non_existent_tasks(self):
        action_url = reverse(
            'DeploySelectedNodesWithTasks',
            kwargs={'cluster_id': self.cluster.id}) + \
            make_orchestrator_uri(self.node_uids)
        out = self.send_put(action_url, self.non_existent)
        self.assertEqual(out.status_code, 400)

    def test_error_on_empty_list_tasks(self):
        action_url = reverse(
            'DeploySelectedNodesWithTasks',
            kwargs={'cluster_id': self.cluster.id}) + \
            make_orchestrator_uri(self.node_uids)
        out = self.send_put(action_url, [])
        self.assertEqual(out.status_code, 400)


class TestDeployMethodVersioning(BaseSelectedNodesTest):

    def assert_deployment_method(self, version, method, mcast):
        self.cluster.release.version = version
        self.db.flush()
        action_url = reverse(
            'DeploySelectedNodes',
            kwargs={'cluster_id': self.cluster.id}) + \
            make_orchestrator_uri(self.node_uids)
        self.send_put(action_url)
        deployment_method = mcast.call_args_list[0][0][1]['method']
        self.assertEqual(deployment_method, method)

    @patch('nailgun.task.task.rpc.cast')
    def test_deploy_is_used_before_61(self, mcast):
        self.assert_deployment_method('2014.2-6.0', 'deploy', mcast)

    @patch('nailgun.task.task.rpc.cast')
    def test_granular_is_used_in_61(self, mcast):
        self.assert_deployment_method('2014.2-6.1', 'granular_deploy', mcast)
