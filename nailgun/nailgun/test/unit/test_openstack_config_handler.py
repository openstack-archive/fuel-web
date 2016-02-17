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
import six.moves.urllib.parse as urlparse

from oslo_serialization import jsonutils

from nailgun import consts
from nailgun.objects.serializers.openstack_config import \
    OpenstackConfigSerializer
from nailgun.test.base import BaseIntegrationTest
from nailgun.utils import reverse


class TestOpenstackConfigHandlers(BaseIntegrationTest):

    def setUp(self):
        super(TestOpenstackConfigHandlers, self).setUp()

        self.env.create_cluster(api=False,
                                status=consts.CLUSTER_STATUSES.operational)
        self.env.create_cluster(api=False,
                                status=consts.CLUSTER_STATUSES.operational)

        self.clusters = self.env.clusters
        self.nodes = self.env.create_nodes(
            3, cluster_id=self.clusters[0].id,
            status=consts.NODE_STATUSES.ready)

        self.env.create_openstack_config(
            cluster_id=self.clusters[0].id, configuration={})
        self.env.create_openstack_config(
            cluster_id=self.clusters[0].id, node_id=self.nodes[1].id,
            configuration={
                'nova_config': 'value_2_1'
            })
        self.env.create_openstack_config(
            cluster_id=self.clusters[0].id, node_id=self.nodes[1].id,
            configuration={
                'nova_config': 'value_1_1'
            })

        self.configs = self.env.openstack_configs

    def create_running_deployment_task(self):
        return self.env.create_task(
            cluster_id=self.clusters[0].id,
            name=consts.TASK_NAMES.deployment,
            status=consts.TASK_STATUSES.running
        ).id

    def check_fail_deploy_running(self, deploy_task_id, resp):
        self.assertEqual(resp.status_code, 403)
        self.assertEqual("Cannot perform the action because there are "
                         "running deployment tasks '{0}'"
                         "".format(deploy_task_id), resp.json_body['message'])

    def test_openstack_config_upload_new(self):
        data = {
            'cluster_id': self.clusters[0].id,
            'node_id': self.nodes[0].id,
            'configuration': {}
        }

        resp = self.app.post(
            reverse('OpenstackConfigCollectionHandler'),
            jsonutils.dumps(data),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 201)
        resp_data = resp.json_body
        self.assertEqual(resp_data['cluster_id'], self.clusters[0].id)
        self.assertEqual(resp_data['node_id'], self.nodes[0].id)

    def test_openstack_config_upload_override(self):
        data = {
            'cluster_id': self.clusters[0].id,
            'node_id': self.nodes[1].id,
            'configuration': {
                'nova_config': 'value_1_2'
            }
        }
        resp = self.app.post(
            reverse('OpenstackConfigCollectionHandler'),
            jsonutils.dumps(data),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 201)
        resp_data = resp.json_body
        self.assertEqual(resp_data['cluster_id'], self.clusters[0].id)
        self.assertEqual(resp_data['node_id'], self.nodes[1].id)

        resp = self.app.get(
            reverse('OpenstackConfigHandler',
                    {'obj_id': self.configs[1].id}),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json_body['is_active'], False)

    def test_openstack_config_upload_fail(self):
        data = {
            'cluster_id': self.clusters[1].id,
            'node_id': self.nodes[1].id,
            'configuration': {}
        }
        resp = self.app.post(
            reverse('OpenstackConfigCollectionHandler'),
            jsonutils.dumps(data),
            headers=self.default_headers, expect_errors=True)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.json_body['message'],
            "Node '{0}' is not assigned to cluster '{1}'".format(
                self.nodes[1].id, self.clusters[1].id))

    def test_openstack_config_upload_fail_not_supported_config(self):
        """Test for uploading an update for not supported OpenStack config"""
        data = {
            'cluster_id': self.clusters[0].id,
            'node_id': self.nodes[0].id,
            'configuration': {
                'not_supported_config': {}
            }
        }

        resp = self.app.post(
            reverse('OpenstackConfigCollectionHandler'),
            jsonutils.dumps(data),
            headers=self.default_headers,
            expect_errors=True)
        self.assertEqual(resp.status_code, 400)
        self.assertRegexpMatches(
            resp.json_body['message'],
            r"Configurations '\w+' can not be updated")

    def test_openstack_config_upload_fail_deploy_running(self):
        deploy_task_id = self.create_running_deployment_task()
        data = {
            'cluster_id': self.clusters[0].id,
            'configuration': {}
        }

        resp = self.app.post(
            reverse('OpenstackConfigCollectionHandler'),
            jsonutils.dumps(data),
            headers=self.default_headers,
            expect_errors=True)
        self.check_fail_deploy_running(deploy_task_id, resp)

    def test_openstack_config_list(self):
        url = self._make_filter_url(cluster_id=self.clusters[0].id)
        resp = self.app.get(url, headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json_body), 2)

        url = self._make_filter_url(
            cluster_id=self.clusters[0].id, node_id=self.nodes[1].id)
        resp = self.app.get(url, headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json_body), 1)

        url = self._make_filter_url(
            cluster_id=self.clusters[0].id, is_active=0)
        resp = self.app.get(url, headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json_body), 1)
        self.assertFalse(resp.json_body[0]['is_active'])

        url = self._make_filter_url(cluster_id=self.clusters[1].id)
        resp = self.app.get(url, headers=self.default_headers)
        self.assertEqual(len(resp.json_body), 0)

    def test_openstack_config_list_fail(self):
        url = self._make_filter_url(
            cluster_id=self.clusters[0].id, node_id=self.nodes[0].id,
            node_role='controller')
        resp = self.app.get(url, headers=self.default_headers,
                            expect_errors=True)
        self.assertEqual(resp.status_code, 400)
        self.assertRegexpMatches(
            resp.json_body['message'],
            r"Parameter '\w+' conflicts with '\w+(, \w+)*'")

    def test_openstack_config_get(self):
        resp = self.app.get(
            reverse('OpenstackConfigHandler',
                    {'obj_id': self.configs[0].id}),
            headers=self.default_headers)

        self.assertEqual(resp.status_code, 200)
        config = resp.json_body
        self.assertDictContainsSubset({
            'cluster_id': self.configs[0].cluster_id,
            'node_id': self.configs[0].node_id,
            'node_role': self.configs[0].node_role,
        }, config)
        self.assertEqual(sorted(config.keys()),
                         sorted(OpenstackConfigSerializer.fields))

    def test_openstack_config_put(self):
        resp = self.app.put(
            reverse('OpenstackConfigHandler',
                    {'obj_id': self.configs[0].id}),
            expect_errors=True)
        self.assertEqual(resp.status_code, 405)

    @mock.patch('objects.Cluster.get_deployment_tasks')
    @mock.patch('nailgun.task.task.rpc.cast')
    def execute_update_open_stack_config(self, mock_rpc, tasks_mock):
        tasks_mock.return_value = [{
            'id': 'upload_configuration',
            'type': 'upload_file',
            'version': '2.0.0',
            'role': '*',
            'parameters': {
                'timeout': 180,
            },
            'refresh_on': ['*']
        }]
        data = {'cluster_id': self.clusters[0].id}
        resp = self.app.put(
            reverse('OpenstackConfigExecuteHandler'),
            jsonutils.dumps(data), headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 202)
        return mock_rpc.call_args_list[0][0][1]

    def test_openstack_config_execute_with_granular_deploy(self):
        self.disable_task_deploy_engine(self.clusters[0])
        message = self.execute_update_open_stack_config()
        self.assertEqual('execute_tasks', message['method'])
        self.assertEqual('update_config_resp', message['respond_to'])
        # there is no task deduplication in granular deployment
        # and some of tasks can be included
        # to result list more than 1 times
        self.assertItemsEqual(
            ((n.uid, 'upload_file') for n in self.clusters[0].nodes),
            {(t['uids'][0], t['type']) for t in message['args']['tasks']}
        )

    def test_openstack_config_execute_with_task_deploy(self):
        message = self.execute_update_open_stack_config()
        self.assertEqual('task_deploy', message['method'])
        self.assertEqual('update_config_resp', message['respond_to'])
        tasks = message['args']['deployment_tasks']
        nodes = [n.uid for n in self.clusters[0].nodes]
        nodes.append(None)
        self.assertItemsEqual(nodes, tasks)
        self.assertEqual(
            'upload_file',
            tasks[nodes[0]][0]['type']
        )

    @mock.patch('objects.OpenstackConfigCollection.find_configs_for_nodes')
    def test_openstack_config_does_not_run_if_no_configs_updated(self, m_conf):
        m_conf.return_value = []
        message = self.execute_update_open_stack_config()
        self.assertEqual('task_deploy', message['method'])
        self.assertEqual('update_config_resp', message['respond_to'])
        tasks = message['args']['deployment_tasks']
        # the null node adds always
        self.assertItemsEqual([None], tasks)

    @mock.patch('nailgun.task.task.rpc.cast')
    def test_openstack_config_execute_force(self, _):
        # Turn node 2 into provisioned state
        self.env.nodes[2].status = consts.NODE_STATUSES.provisioned
        self.db.flush()
        # Try to update OpenStack configuration for cluster
        data = {'cluster_id': self.clusters[0].id}
        resp = self.app.put(
            reverse('OpenstackConfigExecuteHandler'),
            jsonutils.dumps(data), headers=self.default_headers,
            expect_errors=True)
        # Request shouldn't pass a validation
        self.assertEqual(resp.status_code, 400)
        self.assertEqual("Nodes '{0}' are not in status 'ready' and "
                         "can not be updated directly."
                         "".format(self.env.nodes[2].uid),
                         resp.json_body['message'])

        # Try to update OpenStack configuration for cluster with 'force' key
        data = {'cluster_id': self.clusters[0].id,
                'force': True}
        resp = self.app.put(
            reverse('OpenstackConfigExecuteHandler'),
            jsonutils.dumps(data), headers=self.default_headers
        )
        # Update OpenStack configuration executed successfully
        self.assertEqual(resp.status_code, 202)

    def test_openstack_config_execute_fail_cluster_not_operational(self):
        self.clusters[0].status = consts.CLUSTER_STATUSES.error
        self.db.flush()
        data = {'cluster_id': self.clusters[0].id}
        resp = self.app.put(
            reverse('OpenstackConfigExecuteHandler'),
            jsonutils.dumps(data), headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json_body['message'],
                         "Cluster should be in the status 'operational'")

    def test_openstack_config_execute_fail_deploy_running(self):
        deploy_task_id = self.create_running_deployment_task()
        data = {'cluster_id': self.clusters[0].id}
        resp = self.app.put(
            reverse('OpenstackConfigExecuteHandler'),
            jsonutils.dumps(data), headers=self.default_headers,
            expect_errors=True
        )
        self.check_fail_deploy_running(deploy_task_id, resp)

    def test_openstack_config_execute_fail_no_ready_nodes(self):
        # Turn node 0 into provisioned state
        self.env.nodes[0].status = consts.NODE_STATUSES.provisioned
        self.env.nodes[1].status = consts.NODE_STATUSES.provisioned
        self.env.nodes[2].status = consts.NODE_STATUSES.provisioned
        self.db.flush()

        # Try to update configuration for node 0
        data = {'cluster_id': self.clusters[0].id}

        resp = self.app.put(
            reverse('OpenstackConfigExecuteHandler'),
            jsonutils.dumps(data), headers=self.default_headers,
            expect_errors=True
        )
        # Request shouldn't pass a validation
        self.assertEqual(resp.status_code, 400)
        self.assertEqual("No nodes in status 'ready'",
                         resp.json_body['message'])

    def test_openstack_config_execute_fail_not_existed_cluster(self):
        # Try to update not existed cluster
        data = {'cluster_id': -1}
        resp = self.app.put(
            reverse('OpenstackConfigExecuteHandler'),
            jsonutils.dumps(data), headers=self.default_headers,
            expect_errors=True
        )
        # Request shouldn't pass a validation
        self.assertEqual(resp.status_code, 404)
        self.assertEqual("Object 'Cluster' with UID=-1 is not found in DB",
                         resp.json_body['message'])

    def test_openstack_config_delete(self):
        obj_id = self.configs[0].id

        resp = self.app.delete(
            reverse('OpenstackConfigHandler',
                    {'obj_id': obj_id}),
            expect_errors=True)
        self.assertEqual(resp.status_code, 204)

        resp = self.app.get(
            reverse('OpenstackConfigHandler',
                    {'obj_id': obj_id}),
            headers=self.default_headers)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json_body['is_active'], False)

        # Try delete already deleted object
        resp = self.app.delete(
            reverse('OpenstackConfigHandler',
                    {'obj_id': obj_id}),
            headers=self.default_headers, expect_errors=True)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.json_body['message'],
            "Configuration '{0}' has been already disabled.".format(obj_id))

    def test_openstack_config_delete_fail_deploy_running(self):
        deploy_task_id = self.create_running_deployment_task()
        resp = self.app.delete(
            reverse('OpenstackConfigHandler',
                    {'obj_id': self.configs[0].id}),
            expect_errors=True)
        self.check_fail_deploy_running(deploy_task_id, resp)

    @classmethod
    def _make_filter_url(cls, **kwargs):
        return '{0}?{1}'.format(
            reverse('OpenstackConfigCollectionHandler'),
            urlparse.urlencode(kwargs))
