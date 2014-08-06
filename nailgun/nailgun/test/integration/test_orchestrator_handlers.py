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

import nailgun

from nailgun import objects

from mock import patch

from nailgun.db.sqlalchemy.models import Cluster
from nailgun.openstack.common import jsonutils
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks
from nailgun.test.base import reverse


def nodes_filter_param(node_ids):
    return '?nodes={0}'.format(','.join(node_ids))


class TestOrchestratorInfoHandlers(BaseIntegrationTest):

    def setUp(self):
        super(TestOrchestratorInfoHandlers, self).setUp()
        self.cluster = self.env.create_cluster(api=False)

    def check_info_handler(
            self, handler_name, get_info, orchestrator_data, default=[]):
        # updating provisioning info
        put_resp = self.app.put(
            reverse(handler_name,
                    kwargs={'cluster_id': self.cluster.id}),
            jsonutils.dumps(orchestrator_data),
            headers=self.default_headers)

        self.assertEqual(put_resp.status_code, 200)
        self.assertEqual(get_info(), orchestrator_data)

        # getting provisioning info
        get_resp = self.app.get(
            reverse(handler_name,
                    kwargs={'cluster_id': self.cluster.id}),
            headers=self.default_headers)

        self.assertEqual(get_resp.status_code, 200)
        self.datadiff(orchestrator_data, jsonutils.loads(get_resp.body))

        # deleting provisioning info
        delete_resp = self.app.delete(
            reverse(handler_name,
                    kwargs={'cluster_id': self.cluster.id}),
            headers=self.default_headers)

        self.assertEqual(delete_resp.status_code, 202)
        self.assertEqual(get_info(), default)

    def test_cluster_provisioning_info(self):
        orchestrator_data = {'engine': {}, 'nodes': []}
        for node in self.env.nodes:
            orchestrator_data['nodes'].append(
                {"field": "test", "uid": node.uid})

        self.check_info_handler(
            'ProvisioningInfo',
            lambda: objects.Cluster.get_provisioning_info(self.cluster),
            orchestrator_data,
            default={})

    def test_cluster_deployment_info(self):
        orchestrator_data = []
        for node in self.env.nodes:
            orchestrator_data.append({"field": "test", "uid": node.uid})
        self.check_info_handler(
            'DeploymentInfo',
            lambda: objects.Cluster.get_deployment_info(self.cluster),
            orchestrator_data)


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
        self.assertEqual(3, len(jsonutils.loads(resp.body)))

    def test_default_provisioning_handler(self):
        resp = self.app.get(
            reverse('DefaultProvisioningInfo',
                    kwargs={'cluster_id': self.cluster.id}),
            headers=self.default_headers)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(3, len(jsonutils.loads(resp.body)['nodes']))

    def test_default_provisioning_handler_for_selected_nodes(self):
        node_ids = [node.uid for node in self.cluster.nodes][:2]
        url = reverse(
            'DefaultProvisioningInfo',
            kwargs={'cluster_id': self.cluster.id}) + \
            nodes_filter_param(node_ids)
        resp = self.app.get(url, headers=self.default_headers)

        self.assertEqual(resp.status_code, 200)
        data = jsonutils.loads(resp.body)['nodes']
        self.assertEqual(2, len(data))
        actual_uids = [node['uid'] for node in data]
        self.assertItemsEqual(actual_uids, node_ids)

    def test_default_deployment_handler_for_selected_nodes(self):
        node_ids = [node.uid for node in self.cluster.nodes][:2]
        url = reverse(
            'DefaultDeploymentInfo',
            kwargs={'cluster_id': self.cluster.id}) + \
            nodes_filter_param(node_ids)
        resp = self.app.get(url, headers=self.default_headers)

        self.assertEqual(resp.status_code, 200)
        data = jsonutils.loads(resp.body)
        self.assertEqual(2, len(data))
        actual_uids = [node['uid'] for node in data]
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


class TestSelectedNodesAction(BaseIntegrationTest):

    def setUp(self):
        super(TestSelectedNodesAction, self).setUp()
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

    def send_empty_put(self, url):
        return self.app.put(
            url, '', headers=self.default_headers, expect_errors=True)

    @fake_tasks(fake_rpc=False, mock_rpc=False)
    @patch('nailgun.rpc.cast')
    def test_start_provisioning_on_selected_nodes(self, mock_rpc):
        action_url = reverse(
            'ProvisionSelectedNodes',
            kwargs={'cluster_id': self.cluster.id}) + \
            nodes_filter_param(self.node_uids)

        self.send_empty_put(action_url)

        args, kwargs = nailgun.task.manager.rpc.cast.call_args
        provisioned_uids = [
            n['uid'] for n in args[1]['args']['provisioning_info']['nodes']]

        self.assertEqual(3, len(provisioned_uids))
        self.assertItemsEqual(self.node_uids, provisioned_uids)

    @fake_tasks(fake_rpc=False, mock_rpc=False)
    @patch('nailgun.rpc.cast')
    def test_start_deployment_on_selected_nodes(self, mock_rpc):
        action_url = reverse(
            'DeploySelectedNodes',
            kwargs={'cluster_id': self.cluster.id}) + \
            nodes_filter_param(self.node_uids)

        self.send_empty_put(action_url)

        args, kwargs = nailgun.task.manager.rpc.cast.call_args
        deployed_uids = [n['uid'] for n in args[1]['args']['deployment_info']]
        self.assertEqual(3, len(deployed_uids))
        self.assertItemsEqual(self.node_uids, deployed_uids)
