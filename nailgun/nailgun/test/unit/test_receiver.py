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

from mock import ANY
from mock import patch

from nailgun import consts
from nailgun.objects import ClusterPlugin
from nailgun.objects import Plugin
from nailgun.rpc.receiver import NailgunReceiver
from nailgun.test import base


class TestNailgunReceiver(base.BaseTestCase):

    def setUp(self):
        super(TestNailgunReceiver, self).setUp()

        self.cluster = self.env.create(
            status=consts.CLUSTER_STATUSES.operational,
            nodes_kwargs=[
                {'roles': ['controller'],
                 'status': consts.NODE_STATUSES.ready}])

        for i in range(2):
            meta = self.env.get_default_plugin_metadata(
                name='name{0}'.format(i),
                title='title{0}'.format(i),
                description='description{0}'.format(i))

            self.plugin = Plugin.create(meta)
            self.cluster.plugins.append(self.plugin)
            ClusterPlugin.set_attributes(self.cluster.id,
                                         self.plugin.id,
                                         enabled=True)

        self.task = self.env.create_task(
            name=consts.TASK_NAMES.deployment,
            status=consts.TASK_STATUSES.ready,
            cluster_id=self.cluster.id)

    def test_success_action_with_plugins(self):
        data = NailgunReceiver._success_action(
            self.task, 'ready', 100, self.env.nodes
        )
        self.assertRegexpMatches(
            data['message'],
            "Deployment of environment '[^\s]+' is done."
            "\n\n"
            "Plugin name\d is deployed. description\d\n"
            "Plugin name\d is deployed. description\d")

    def test_master_uid_in_deploy_resp(self):
        node_resp = {
            "task_uuid": self.task.uuid,
            "nodes": [
                {"status": "error", "hook": None, "error_type": "deploy",
                 "role": "hook", "uid": "master"}]}
        NailgunReceiver.deploy_resp(**node_resp)
        self.assertEqual(self.task.status, 'error')

        task_resp = {
            "status": "error",
            "task_uuid": self.task.uuid,
            "error": "Method granular_deploy."}
        NailgunReceiver.deploy_resp(**task_resp)
        self.assertEqual(self.task.status, 'error')
        self.assertIn(task_resp['error'], self.task.message)

    @patch('nailgun.rpc.receiver.notifier.notify')
    def test_multiline_error_message(self, mnotify):
        task_resp = {
            "status": "error",
            "task_uuid": self.task.uuid,
            "error": "Method granular_deploy.\n\n Something Something"}
        NailgunReceiver.deploy_resp(**task_resp)
        mnotify.assert_called_with(
            task_resp['status'],
            u'Deployment has failed. Method granular_deploy.',
            self.cluster.id,
            task_uuid=None,
            node_id=None
        )

    @patch('nailgun.objects.Task.update_verify_networks')
    def test_check_repositories_resp_success(self, update_verify_networks):
        # since check_repositories and check_repositories_with_setup
        # have same structure of response data we may test both of the
        # response methods here
        repo_check_message = {
            "status": "ready",
            "progress": 100,
            "task_uuid": self.task.uuid,
            "nodes": [{
                "status": 0,
                "err": "",
                "out": "",
                "uid": "1"}]}
        for resp_method in ('check_repositories_resp',
                            'check_repositories_with_setup_resp'):
            getattr(NailgunReceiver, resp_method)(**repo_check_message)

            update_verify_networks.assert_called_with(
                self.task, 'ready', 100, '', {})

    @patch('nailgun.objects.Task.update_verify_networks')
    def test_check_repositories_resp_error(self, update_verify_networks):
        # ditto as in previous test case
        urls = ['url2', 'url1', 'url3', 'url1']
        repo_check_message = {
            "status": "ready",
            "progress": 100,
            "task_uuid": self.task.uuid,
            "nodes": [
                {
                    "status": 1,
                    "out": {"failed_urls": urls},
                    "err": "",
                    "uid": self.cluster.nodes[0].uid
                },
                {
                    "status": 1,
                    "out": {"failed_urls": urls},
                    "err": "",
                    "uid": consts.MASTER_NODE_UID
                }
            ]}

        expected_err_msg = {
            'check_repositories_resp': (
                r'Repo availability verification'
                ' failed on following nodes {0}, {1}.\n '
                'Following repos are not available - '
                .format(consts.MASTER_NODE_NAME,
                        self.cluster.nodes[0].name)
            ),
            'check_repositories_with_setup_resp': (
                r'Repo availability verification'
                ' using public network'
                ' failed on following nodes {0}, {1}.\n '
                'Following repos are not available - '
                .format(consts.MASTER_NODE_NAME,
                        self.cluster.nodes[0].name)
            ),
        }
        for resp_method in expected_err_msg:
            getattr(NailgunReceiver, resp_method)(**repo_check_message)
            update_verify_networks.assert_called_with(
                self.task, 'error', 100, ANY, {})
            actual_msg = update_verify_networks.call_args[0][3]

            self.assertIn(', '.join(set(urls)), actual_msg)
            self.assertIn(
                expected_err_msg[resp_method],
                actual_msg,
            )

    @patch('nailgun.rpc.receiver.notifier.notify')
    def test_notify_provision(self, notify_checker):
        NailgunReceiver._notify(
            self.task,
            "done",
            "Test error.",
            "123",
            self.task.uuid
        )
        notify_checker.assert_called_with(
            "done",
            u'Test error.',
            self.task.cluster_id,
            node_id="123",
            task_uuid=self.task.uuid
        )

    @patch('nailgun.rpc.receiver.notifier.notify')
    def test_notify_provision_sub_task(self, notify_checker):
        sub_task = self.env.create_task(
            name=consts.TASK_NAMES.provision,
            status=consts.TASK_STATUSES.ready,
            cluster_id=self.cluster.id,
            parent_id=self.task.id
        )
        NailgunReceiver._notify(
            sub_task,
            "done",
            "Test error.",
            "123",
            sub_task.uuid
        )
        self.assertEqual(0, notify_checker.call_count)

    @patch('nailgun.rpc.receiver.notifier.notify')
    def test_notify_deployment(self, notify_checker):
        NailgunReceiver._notify(
            self.task,
            "done",
            "Test error.",
            "123",
            self.task.uuid
        )
        notify_checker.assert_called_with(
            "done",
            u'Test error.',
            self.task.cluster_id,
            node_id="123",
            task_uuid=self.task.uuid
        )

    @patch('nailgun.rpc.receiver.notifier.notify')
    def test_notify_deployment_sub_task(self, notify_checker):
        sub_task = self.env.create_task(
            name=consts.TASK_NAMES.deployment,
            status=consts.TASK_STATUSES.ready,
            cluster_id=self.cluster.id,
            parent_id=self.task.id
        )
        NailgunReceiver._notify(
            sub_task,
            "done",
            "Test error.",
            "123",
            sub_task.uuid
        )
        notify_checker.assert_called_with(
            "done",
            u'Test error.',
            sub_task.cluster_id,
            node_id="123",
            task_uuid=sub_task.uuid
        )

    def test_transaction_resp_update_node_attributes(self):
        task = self.env.create_task(
            name=consts.TASK_NAMES.deployment,
            status=consts.TASK_STATUSES.running,
            cluster_id=self.cluster.id
        )
        node = self.cluster.nodes[0]
        node.status = consts.NODE_STATUSES.provisioned
        node.progress = 1
        node.pending_addition = True
        NailgunReceiver.transaction_resp(
            task_uuid=task.uuid,
            nodes=[{
                'uid': node.uid, 'progress': 50, 'pending_addition': False
            }]
        )
        self.db.refresh(node)
        self.assertEqual(50, node.progress)
        self.assertFalse(node.pending_addition)

    @patch('nailgun.rpc.receiver.notifier.notify')
    def test_transaction_resp_update_transaction_status(self, _):
        task = self.env.create_task(
            name=consts.TASK_NAMES.deployment,
            status=consts.TASK_STATUSES.running,
            cluster_id=self.cluster.id
        )
        NailgunReceiver.transaction_resp(
            task_uuid=task.uuid,
            status=consts.TASK_STATUSES.ready
        )
        self.db.refresh(task)
        self.assertEqual(consts.TASK_STATUSES.ready, task.status)

    @patch('nailgun.rpc.receiver.notifier.notify')
    def test_transaction_resp_does_not_update_nodes_if_dry_run(self, _):
        task = self.env.create_task(
            name=consts.TASK_NAMES.deployment,
            status=consts.TASK_STATUSES.running,
            cluster_id=self.cluster.id,
            dry_run=True
        )
        self.cluster.status = consts.CLUSTER_STATUSES.operational
        node = self.cluster.nodes[0]
        node.status = consts.NODE_STATUSES.provisioned
        NailgunReceiver.transaction_resp(
            task_uuid=task.uuid,
            status=consts.TASK_STATUSES.ready,
            nodes=[{'uid': node.uid, 'status': consts.NODE_STATUSES.ready}]
        )
        self.db.refresh(task)
        self.db.refresh(node)
        self.db.refresh(self.cluster)
        self.assertEqual(consts.TASK_STATUSES.ready, task.status)
        self.assertEqual(consts.NODE_STATUSES.provisioned, node.status)
        self.assertEqual(
            consts.CLUSTER_STATUSES.operational, self.cluster.status
        )

    def test_transaction_resp_does_not_fail_on_virtual_nodes(self):
        task = self.env.create_task(
            name=consts.TASK_NAMES.deployment,
            status=consts.TASK_STATUSES.running,
            cluster_id=self.cluster.id,
            dry_run=True
        )

        NailgunReceiver.transaction_resp(
            task_uuid=task.uuid,
            status=consts.TASK_STATUSES.running,
            nodes=[
                {
                    'uid': consts.MASTER_NODE_UID,
                    'status': consts.NODE_STATUSES.provisioned,
                },
                {
                    # cluster node uid is null
                    'uid': None,
                    'status': consts.NODE_STATUSES.provisioned,
                },
            ])
