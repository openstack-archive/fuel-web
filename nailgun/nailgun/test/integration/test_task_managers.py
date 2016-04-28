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

import time

import mock
import netaddr
import yaml

from sqlalchemy import sql

import nailgun
import nailgun.rpc as rpc

from nailgun import consts
from nailgun import objects

from nailgun.consts import ACTION_TYPES
from nailgun.consts import NODE_STATUSES
from nailgun.consts import TASK_NAMES
from nailgun.consts import TASK_STATUSES

from nailgun.db.sqlalchemy import models
from nailgun import errors
from nailgun.rpc.receiver import NailgunReceiver
from nailgun.task.helpers import TaskHelper
from nailgun.task import manager
from nailgun.task import task
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks
from nailgun.utils import reverse


class TestTaskManagers(BaseIntegrationTest):

    def check_node_presence(self, nodes_count):
        return self.db.query(models.Node).count() == nodes_count

    def check_cluster_deletion_task(self, task_):
        self.assertEqual(task_.name, consts.TASK_NAMES.cluster_deletion)
        self.assertEqual(task_.status, consts.TASK_STATUSES.ready)
        self.assertEqual(task_.progress, 100)
        self.assertEqual(task_.cluster_id, None)
        self.assertNotEqual(task_.deleted_at, None)

    def set_history_ready(self):
        objects.DeploymentHistoryCollection.all().update(
            {'status': consts.HISTORY_TASK_STATUSES.ready})

    @fake_tasks(override_state={"progress": 100, "status": "ready"})
    def test_deployment_task_managers(self):
        cluster = self.env.create(
            nodes_kwargs=[
                {"pending_addition": True},
                {"pending_deletion": True,
                 'status': NODE_STATUSES.provisioned},
            ]
        )
        supertask = self.env.launch_deployment(cluster['id'])
        self.env.refresh_nodes()
        self.assertEqual(supertask.name, TASK_NAMES.deploy)
        self.assertEqual(supertask.status, consts.TASK_STATUSES.ready)
        # we have three subtasks here
        # deletion
        # provision
        # deployment
        self.assertEqual(len(supertask.subtasks), 3)
        # provisioning task has less weight then deployment
        provision_task = filter(
            lambda t: t.name == TASK_NAMES.provision, supertask.subtasks)[0]
        self.assertEqual(provision_task.weight, 0.4)

        cluster_name = cluster['name']
        self.assertIn(
            u"Successfully removed 1 node(s). No errors occurred",
            supertask.message
        )
        self.assertIn(
            u"Provision of environment '{0}' is done.".format(cluster_name),
            supertask.message
        )
        self.assertIn(
            u"Deployment of environment '{0}' is done.".format(cluster_name),
            supertask.message
        )
        self.env.refresh_nodes()
        for n in filter(
            lambda n: n.cluster_id == cluster['id'],
            self.env.nodes
        ):
            self.assertEqual(n.status, NODE_STATUSES.ready)
            self.assertEqual(n.progress, 100)

    @mock.patch('nailgun.task.task.rpc.cast')
    def test_settings_saved_in_transaction(self, _):
        self.env.create(
            nodes_kwargs=[
                {"pending_addition": True},
                {"pending_deletion": True,
                 'status': NODE_STATUSES.provisioned},
            ]
        )
        cluster = self.env.clusters[-1]
        supertask = self.env.launch_deployment(cluster.id)
        self.assertNotEqual(TASK_STATUSES.error, supertask.status)
        deployment_task = next(
            t for t in supertask.subtasks if t.name == TASK_NAMES.deployment
        )
        self.datadiff(
            {'editable': objects.Cluster.get_editable_attributes(cluster)},
            objects.Transaction.get_cluster_settings(deployment_task)
        )
        self.datadiff(
            objects.Cluster.get_network_attributes(cluster),
            objects.Transaction.get_network_settings(deployment_task),
        )

    @mock.patch('nailgun.task.task.rpc.cast')
    def test_deployment_info_saves_in_transaction(self, _):
        self.check_deployment_info_was_saved_in_transaction(
            'mitaka-9.0', True, True
        )
        self.check_deployment_info_was_saved_in_transaction(
            'liberty-8.0', True, False
        )
        self.check_deployment_info_was_saved_in_transaction(
            '2015.1.0-7.0', False, False
        )

    def check_deployment_info_was_saved_in_transaction(
            self, release_ver, is_task_deploy, is_lcm
    ):
        self.env.create(
            nodes_kwargs=[
                {"pending_addition": True},
                {"pending_deletion": True,
                 'status': NODE_STATUSES.provisioned},
            ],
            release_kwargs={
                'operating_system': consts.RELEASE_OS.ubuntu,
                'version': release_ver
            },
        )
        cluster = self.env.clusters[-1]
        if not is_task_deploy:
            self.env.disable_task_deploy(cluster)

        nodes_ids = [n.uid for n in cluster.nodes if not n.pending_deletion]
        supertask = self.env.launch_deployment(cluster.id)
        self.assertNotEqual(TASK_STATUSES.error, supertask.status)
        deployment_task = next(
            t for t in supertask.subtasks if t.name == TASK_NAMES.deployment
        )
        info = objects.Transaction.get_deployment_info(deployment_task)
        # information about master node should be in deployment info
        if is_lcm:
            nodes_ids.append(consts.MASTER_NODE_UID)
        # check that deployment info contains information about all nodes
        # that are not deleted
        self.assertItemsEqual(nodes_ids, info)

    @mock.patch('nailgun.task.task.rpc.cast')
    @mock.patch('objects.Cluster.get_deployment_tasks')
    def test_deployment_tasks_assigned_for_primary_roles(
            self, tasks_mock, rpc_mock
    ):
        tasks_mock.return_value = [
            {
                'id': 'primary_test', 'parameters': {}, 'type': 'puppet',
                'roles': ['primary-controller'], 'version': '2.1.0',
            },
            {
                'id': 'test', 'parameters': {}, 'type': 'puppet',
                'roles': ['controller'], 'version': '2.1.0',
            }
        ]
        self.env.create(
            nodes_kwargs=[
                {"pending_addition": True, "pending_roles": ['controller']},
                {"pending_addition": True, "pending_roles": ['controller']},
            ],
            release_kwargs={
                'operating_system': consts.RELEASE_OS.ubuntu,
                'version': 'mitaka-9.0',
            },
        )
        cluster = self.env.clusters[-1]
        supertask = self.env.launch_deployment(cluster.id)
        self.assertNotEqual(TASK_STATUSES.error, supertask.status)
        tasks_graph = rpc_mock.call_args[0][1][1]['args']['tasks_graph']
        self.assertEqual(
            ['primary_test'],
            [x['id'] for x in tasks_graph[cluster.nodes[0].uid]]
        )
        self.assertEqual(
            ['test'],
            [x['id'] for x in tasks_graph[cluster.nodes[1].uid]]
        )

    @fake_tasks()
    @mock.patch('nailgun.lcm.transaction_serializer.settings',
                LCM_CHECK_TASK_VERSION=True)
    @mock.patch('objects.Cluster.get_deployment_tasks')
    @mock.patch('objects.Cluster.is_propagate_task_deploy_enabled')
    def test_adaptation_legacy_tasks(self, propagate_mock, tasks_mock, _):
        tasks_mock.return_value = [
            {
                'id': 'task', 'parameters': {}, 'type': 'puppet',
                'roles': ['controller'], 'version': '1.0.0',
            },
            {
                'id': 'controller', 'type': 'group', 'roles': ['controller']
            }
        ]
        self.env.create(
            nodes_kwargs=[
                {"pending_addition": True, "pending_roles": ['controller']},
                {"pending_addition": True, "pending_roles": ['controller']},
            ],
            release_kwargs={
                'operating_system': consts.RELEASE_OS.ubuntu,
                'version': 'liberty-9.0',
            }
        )
        cluster = self.env.clusters[-1]
        propagate_mock.return_value = False
        supertask = self.env.launch_deployment(cluster.id)
        self.assertEqual(TASK_STATUSES.error, supertask.status)
        self.assertIn("Task 'task'", supertask.message)
        propagate_mock.return_value = True
        supertask = self.env.launch_deployment(cluster.id)
        self.assertEqual(TASK_STATUSES.ready, supertask.status)

    @fake_tasks(fake_rpc=False, mock_rpc=True)
    def test_write_action_logs(self, _):
        self.env.create(
            nodes_kwargs=[
                {"pending_addition": True},
                {"pending_addition": True},
                {"pending_deletion": True}
            ]
        )

        deployment_task = self.env.launch_deployment()

        for subtask in deployment_task.subtasks:
            action_log = objects.ActionLog.get_by_kwargs(
                task_uuid=subtask.uuid,
                action_name=subtask.name
            )

            self.assertIsNotNone(action_log)
            self.assertEqual(subtask.parent_id,
                             action_log.additional_info['parent_task_id'])
            self.assertIn(action_log.action_name, TASK_NAMES)
            self.assertEqual(action_log.action_type, ACTION_TYPES.nailgun_task)

            if action_log.additional_info["operation"] in \
                    (TASK_NAMES.check_networks,
                     TASK_NAMES.check_before_deployment):
                self.assertIsNotNone(action_log.end_timestamp)
                self.assertIn("ended_with_status", action_log.additional_info)
                self.assertIn("message", action_log.additional_info)
                self.assertEqual(action_log.additional_info["message"], "")
                self.assertIn("output", action_log.additional_info)

    def test_update_action_logs_after_empty_cluster_deletion(self):
        self.env.create_cluster()
        self.env.delete_environment()

        al = objects.ActionLogCollection.filter_by(
            None, action_type=consts.ACTION_TYPES.nailgun_task).first()

        self.assertIsNotNone(al.end_timestamp)
        self.assertEqual(al.additional_info["ended_with_status"],
                         consts.TASK_STATUSES.ready)
        self.assertEqual(al.additional_info["message"], "")
        self.assertEqual(al.additional_info["output"], {})

    def test_action_log_created_for_check_before_deployment_with_error(self):
        self.env.create(
            nodes_kwargs=[
                {"pending_addition": True, "online": False}
            ]
        )

        supertask = self.env.launch_deployment()

        action_logs = objects.ActionLogCollection.filter_by(
            None, action_type=consts.ACTION_TYPES.nailgun_task).all()

        # we have three action logs for the next tasks
        # deletion
        # provision
        # deployment
        self.assertEqual(len(action_logs), 3)
        for al in action_logs:
            self.assertEqual(al.action_type, ACTION_TYPES.nailgun_task)
            if al.additional_info["operation"] == TASK_NAMES.deploy:
                self.assertIsNone(al.additional_info["parent_task_id"])
                self.assertEqual(al.task_uuid, supertask.uuid)
            else:
                self.assertIsNotNone(al.end_timestamp)
                self.assertIn("ended_with_status", al.additional_info)
                self.assertIn("message", al.additional_info)
                self.assertEqual(al.additional_info["message"], "")
                self.assertIn("output", al.additional_info)

                if (
                    al.additional_info["operation"] ==
                    TASK_NAMES.check_networks
                ):
                    self.assertEqual(al.additional_info["ended_with_status"],
                                     TASK_STATUSES.ready)
                    self.assertEqual(al.additional_info["parent_task_id"],
                                     supertask.id)
                elif (
                    al.additional_info["operation"] ==
                    TASK_NAMES.check_before_deployment
                ):
                    self.assertEqual(al.additional_info["ended_with_status"],
                                     TASK_STATUSES.error)
                    self.assertEqual(al.additional_info["parent_task_id"],
                                     supertask.id)

    @fake_tasks(fake_rpc=False, mock_rpc=False)
    @mock.patch('nailgun.rpc.cast')
    def test_do_not_send_node_to_orchestrator_which_has_status_discover(
            self, _):

        self.env.create(
            nodes_kwargs=[
                {'pending_deletion': True, 'status': 'discover'}])

        self.env.launch_deployment()

        args, kwargs = nailgun.task.manager.rpc.cast.call_args_list[0]
        self.assertEqual(len(args[1]['args']['nodes']), 0)

        self.env.refresh_nodes()
        for n in self.env.nodes:
            self.assertEqual(len(self.env.nodes), 0)

    @fake_tasks(fake_rpc=False, mock_rpc=False)
    @mock.patch('nailgun.rpc.cast')
    def test_send_to_orchestrator_offline_nodes(self, _):
        self.env.create(
            nodes_kwargs=[
                {'pending_deletion': True,
                 'status': 'ready',
                 'online': False}])

        self.env.launch_deployment()

        args, kwargs = nailgun.task.manager.rpc.cast.call_args_list[0]
        self.assertEqual(len(args[1]['args']['nodes']), 1)

    @fake_tasks(fake_rpc=False, mock_rpc=False)
    @mock.patch('nailgun.rpc.cast')
    def test_update_nodes_info_on_node_removal(self, _):
        self.env.create(
            cluster_kwargs={
                'status': consts.CLUSTER_STATUSES.operational,
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': consts.NEUTRON_SEGMENT_TYPES.gre,
            },
            nodes_kwargs=[
                {'status': consts.NODE_STATUSES.ready,
                 'roles': ['controller']},
                {'status': consts.NODE_STATUSES.ready, 'roles': ['compute'],
                 'pending_deletion': True},
                {'status': consts.NODE_STATUSES.ready, 'roles': ['compute']},
                {'status': consts.NODE_STATUSES.ready, 'roles': ['compute']},
            ])

        objects.Cluster.prepare_for_deployment(self.env.clusters[0])
        self.env.launch_deployment()

        args, _ = nailgun.task.manager.rpc.cast.call_args_list[1]
        for message in args[1]:
            if message['method'] == 'execute_tasks':
                self.assertEqual(message['respond_to'], 'deploy_resp')
                execute_tasks = message
                break
        else:
            self.fail("'execute_tasks' method not found")

        def is_upload_nodes(task):
            return 'nodes.yaml' in task['parameters'].get('path', '')

        def is_update_hosts(task):
            return 'hosts.pp' in task['parameters'].get('puppet_manifest', '')

        tasks = execute_tasks['args']['tasks']
        self.assertIsNotNone(next((
            t for t in tasks if is_upload_nodes(t)), None))
        self.assertIsNotNone(next((
            t for t in tasks if is_update_hosts(t)), None))

    @mock.patch('nailgun.task.manager.rpc.cast')
    def test_do_not_redeploy_nodes_in_ready_status(self, mcast):
        self.env.create(
            nodes_kwargs=[
                {'pending_addition': False,
                 'roles': ['controller'],
                 'status': consts.NODE_STATUSES.ready},
                {'pending_addition': True,
                 'roles': ['compute'],
                 'status': consts.NODE_STATUSES.discover},
            ],
        )
        self.db.flush()
        node_db = self.env.nodes[1]

        supertask = self.env.launch_deployment()
        self.assertEqual(supertask.name, consts.TASK_NAMES.deploy)
        self.assertEqual(supertask.status, consts.TASK_STATUSES.pending)

        args, _ = mcast.call_args_list[0]
        provisioning_info = args[1][0]['args']['provisioning_info']
        deployment_info = args[1][1]['args']['deployment_info']

        # only one node should be provisioned (the second one)
        self.assertEqual(1, len(provisioning_info['nodes']))
        self.assertEqual(node_db.uid, provisioning_info['nodes'][0]['uid'])

        # only one node should be deployed (the second one)
        self.assertEqual(1, len(deployment_info))
        self.assertEqual(node_db.uid, deployment_info[0]['uid'])

    @fake_tasks()
    def test_deployment_fails_if_node_offline(self):
        cluster = self.env.create_cluster(api=True)
        self.env.create_node(
            cluster_id=cluster['id'],
            roles=["controller"],
            pending_addition=True)
        offline_node = self.env.create_node(
            cluster_id=cluster['id'],
            roles=["compute"],
            online=False,
            name="Offline node",
            pending_addition=True)
        self.env.create_node(
            cluster_id=cluster['id'],
            roles=["compute"],
            pending_addition=True)
        supertask = self.env.launch_deployment()
        self.assertEqual(supertask.status, consts.TASK_STATUSES.error)

        msg = ('Nodes "{0}" are offline. Remove them from environment '
               'and try again.'.format(offline_node.full_name))
        self.assertEqual(supertask.message, msg)
        # Do not move cluster to error state
        # in case if cluster new and before
        # validation failed
        self.assertEqual(self.env.clusters[0].status, 'new')

    @fake_tasks()
    def test_deployment_fails_if_node_to_redeploy_is_offline(self):
        cluster = self.env.create_cluster(
            api=True,
            status=consts.CLUSTER_STATUSES.operational)
        offline_node = self.env.create_node(
            cluster_id=cluster['id'],
            roles=["controller"],
            online=False,
            name="Offline node to be redeployed",
            status=consts.NODE_STATUSES.ready)
        self.env.create_node(
            cluster_id=cluster['id'],
            roles=["controller"],
            pending_addition=True)
        self.env.create_node(
            cluster_id=cluster['id'],
            roles=["compute"],
            pending_addition=True)
        supertask = self.env.launch_deployment()
        self.assertEqual(supertask.status, consts.TASK_STATUSES.error)

        msg = ('Nodes "{0}" are offline. Remove them from environment '
               'and try again.'.format(offline_node.full_name))
        self.assertEqual(supertask.message, msg)

        self.assertEqual(self.env.clusters[0].status, 'error')

    @fake_tasks(override_state={"progress": 100, "status": "ready"})
    def test_redeployment_works(self):
        self.env.create(
            nodes_kwargs=[
                {"pending_addition": True},
                {"pending_addition": True},
                {"pending_addition": True},
                {"roles": ["compute"], "pending_addition": True}
            ]
        )
        supertask = self.env.launch_deployment()
        self.assertEqual(supertask.status, consts.TASK_STATUSES.ready)
        self.env.refresh_nodes()

        self.env.create_node(
            cluster_id=self.env.clusters[0].id,
            roles=["controller"],
            pending_addition=True
        )

        supertask = self.env.launch_deployment()
        self.assertEqual(supertask.status, consts.TASK_STATUSES.ready)
        self.env.refresh_nodes()
        for n in self.env.nodes:
            self.assertEqual(n.status, 'ready')
            self.assertEqual(n.progress, 100)

    def test_deletion_empty_cluster_task_manager(self):
        # (mihgen): we synchronously call rpc receiver for empty cluster
        # that's why there is no need to mock rpc now
        # see task/task.py#L513 (DeletionTask.execute)
        cluster = self.env.create_cluster(api=True)
        resp = self.app.delete(
            reverse(
                'ClusterHandler',
                kwargs={'obj_id': cluster['id']}),
            headers=self.default_headers
        )
        self.assertEqual(202, resp.status_code)

        notification = self.db.query(models.Notification)\
            .filter(models.Notification.topic == "done")\
            .filter(models.Notification.message == "Environment '%s' and all "
                    "its nodes are deleted" % cluster["name"]).first()
        self.assertIsNotNone(notification)

        tasks = self.db.query(models.Task).all()
        self.assertEqual(len(tasks), 1)

        self.check_cluster_deletion_task(tasks[0])

    @fake_tasks()
    def test_deletion_cluster_task_manager(self):
        self.env.create(
            nodes_kwargs=[
                {"status": "ready", "progress": 100},
                {"roles": ["compute"], "status": "ready", "progress": 100},
                {"roles": ["compute"], "pending_addition": True},
            ]
        )
        cluster_id = self.env.clusters[0].id
        cluster_name = self.env.clusters[0].name
        resp = self.app.delete(
            reverse(
                'ClusterHandler',
                kwargs={'obj_id': cluster_id}),
            headers=self.default_headers
        )
        self.assertEqual(202, resp.status_code)

        notification = self.db.query(models.Notification)\
            .filter(models.Notification.topic == "done")\
            .filter(models.Notification.message == "Environment '%s' and all "
                    "its nodes are deleted" % cluster_name).first()
        self.assertIsNotNone(notification)
        self.assertIsNone(self.db.query(models.Cluster).get(cluster_id))

        tasks = self.db.query(models.Task).all()
        self.assertEqual(len(tasks), 1)

        self.check_cluster_deletion_task(tasks[0])

    @fake_tasks(tick_interval=10, tick_count=5)
    def test_deletion_clusters_one_by_one(self):
        self.env.create(
            nodes_kwargs=[
                {"roles": ["compute"], "status": "ready", "progress": 100},
                {"roles": ["compute"], "status": "ready", "progress": 100},
                {"roles": ["compute"], "status": "ready", "progress": 100},
                {"roles": ["controller"], "status": "ready", "progress": 100},
                {"roles": ["controller"], "status": "ready", "progress": 100},
                {"roles": ["cinder"], "status": "ready", "progress": 100},
            ]
        )
        cluster1_id = self.env.clusters[0].id
        self.env.create_cluster(api=True)
        cluster2_id = self.env.clusters[1].id
        cluster_names = [cluster.name for cluster in self.env.clusters]

        resp = self.app.delete(
            reverse(
                'ClusterHandler',
                kwargs={'obj_id': cluster1_id}),
            headers=self.default_headers
        )
        self.assertEqual(202, resp.status_code)

        resp = self.app.delete(
            reverse(
                'ClusterHandler',
                kwargs={'obj_id': cluster2_id}),
            headers=self.default_headers
        )
        self.assertEqual(202, resp.status_code)

        timer = time.time()
        timeout = 15

        clstr1 = self.db.query(models.Cluster).get(cluster1_id)
        clstr2 = self.db.query(models.Cluster).get(cluster2_id)
        while clstr1 or clstr2:
            time.sleep(1)
            try:
                self.db.refresh(clstr1 or clstr2)
            except Exception:
                break
            if time.time() - timer > timeout:
                raise Exception("Cluster deletion seems to be hanged")

        for name in cluster_names:
            notification = self.db.query(models.Notification)\
                .filter(models.Notification.topic == "done")\
                .filter(models.Notification.message == "Environment '%s' and "
                        "all its nodes are deleted" % name)
            self.assertIsNotNone(notification)

        tasks = self.db.query(models.Task).all()
        self.assertEqual(len(tasks), 2)

        for task_ in tasks:
            self.check_cluster_deletion_task(task_)

    @fake_tasks(recover_nodes=False, fake_rpc=False)
    def test_deletion_during_deployment(self, mock_rpc):
        self.env.create(
            nodes_kwargs=[
                {"status": "ready", "pending_addition": True},
            ]
        )
        cluster_id = self.env.clusters[0].id
        resp = self.app.put(
            reverse(
                'ClusterChangesHandler',
                kwargs={'cluster_id': cluster_id}),
            headers=self.default_headers
        )
        deploy_uuid = resp.json_body['uuid']
        NailgunReceiver.provision_resp(
            task_uuid=deploy_uuid,
            status=consts.TASK_STATUSES.running,
            progress=50,
        )

        resp = self.app.delete(
            reverse(
                'ClusterHandler',
                kwargs={'obj_id': cluster_id}),
            headers=self.default_headers
        )
        task_delete = self.db.query(models.Task).filter_by(
            uuid=resp.json_body['uuid'],
        ).first()
        NailgunReceiver.remove_cluster_resp(
            task_uuid=task_delete.uuid,
            status=consts.TASK_STATUSES.ready,
            progress=100,
        )

        task_deploy = self.db.query(models.Task).filter_by(
            uuid=deploy_uuid
        ).first()
        self.assertIsNone(task_deploy)
        task_delete = self.db.query(models.Task).filter_by(
            cluster_id=cluster_id,
            name="cluster_deletion"
        ).first()
        self.assertIsNone(task_delete)

    @fake_tasks(override_state={"progress": 100, "status": "ready"})
    def test_deletion_cluster_ha_3x3(self):
        self.env.create(
            cluster_kwargs={
                "api": True,
            },
            nodes_kwargs=[
                {"roles": ["controller"], "pending_addition": True},
                {"roles": ["compute"], "pending_addition": True}
            ] * 3
        )
        cluster_id = self.env.clusters[0].id
        cluster_name = self.env.clusters[0].name
        supertask = self.env.launch_deployment()
        self.assertEqual(supertask.status, consts.TASK_STATUSES.ready)

        resp = self.app.delete(
            reverse(
                'ClusterHandler',
                kwargs={'obj_id': cluster_id}),
            headers=self.default_headers
        )
        self.assertEqual(202, resp.status_code)

        timer = time.time()
        timeout = 15
        clstr = self.db.query(models.Cluster).get(cluster_id)
        while clstr:
            time.sleep(1)
            try:
                self.db.refresh(clstr)
            except Exception:
                break
            if time.time() - timer > timeout:
                raise Exception("Cluster deletion seems to be hanged")

        notification = self.db.query(models.Notification)\
            .filter(models.Notification.topic == "done")\
            .filter(models.Notification.message == "Environment '%s' and all "
                    "its nodes are deleted" % cluster_name).first()
        self.assertIsNotNone(notification)

        tasks = self.db.query(models.Task).all()
        self.assertEqual(len(tasks), 1)

        self.check_cluster_deletion_task(tasks[0])

    @fake_tasks()
    def test_no_node_no_cry(self):
        cluster = self.env.create_cluster(
            api=True,
            release_kwargs={
                'operating_system': consts.RELEASE_OS.ubuntu,
                'version': 'liberty-8.0'
            },
        )
        cluster_id = cluster['id']
        manager_ = manager.ApplyChangesTaskManager(cluster_id)
        task = models.Task(name='provision', cluster_id=cluster_id,
                           status=consts.TASK_STATUSES.ready)
        self.db.add(task)
        self.db.commit()
        rpc.receiver.NailgunReceiver.deploy_resp(nodes=[
            {'uid': 666, 'id': 666, 'status': 'discover'}
        ], task_uuid=task.uuid)
        self.assertRaises(errors.WrongNodeStatus, manager_.execute)

    @fake_tasks()
    @mock.patch.object(task.DeletionTask, 'execute')
    def test_deletion_task_called(self, mdeletion_execute):
        cluster = self.env.create_cluster()
        cluster_id = cluster['id']
        node_db = self.env.create_node(
            api=False,
            cluster_id=cluster['id'],
            pending_addition=False,
            pending_deletion=True,
            status=NODE_STATUSES.ready,
            roles=['controller'])

        manager_ = manager.ApplyChangesTaskManager(cluster_id)
        manager_.execute()

        self.assertEqual(mdeletion_execute.call_count, 1)
        nodes = mdeletion_execute.call_args[0][1]
        # unfortunately assertItemsEqual does not recurse into dicts
        self.assertItemsEqual(
            nodes['nodes_to_delete'],
            task.DeletionTask.prepare_nodes_for_task(
                [node_db])['nodes_to_delete']
        )
        self.assertItemsEqual(
            nodes['nodes_to_restore'],
            task.DeletionTask.prepare_nodes_for_task(
                [node_db])['nodes_to_restore']
        )

    @fake_tasks()
    @mock.patch.object(task.DeletionTask, 'execute')
    def test_deletion_task_w_check_ceph(self, mdeletion_execute):
        cluster = self.env.create_cluster()
        cluster_id = cluster['id']
        self.env.create_node(
            api=False,
            cluster_id=cluster['id'],
            pending_addition=False,
            pending_deletion=True,
            status=NODE_STATUSES.ready,
            roles=['controller'])

        manager_ = manager.ApplyChangesTaskManager(cluster_id)
        manager_.execute()

        self.assertEqual(mdeletion_execute.call_count, 1)
        kwargs = mdeletion_execute.call_args[1]
        self.assertEqual(kwargs['check_ceph'], True)

    @fake_tasks()
    def test_no_changes_no_cry(self):
        self.env.create(
            nodes_kwargs=[
                {"status": "ready"}
            ],
            release_kwargs={
                'operating_system': consts.RELEASE_OS.ubuntu,
                'version': 'liberty-8.0'
            },
        )
        cluster_db = self.env.clusters[0]
        objects.Cluster.clear_pending_changes(cluster_db)
        manager_ = manager.ApplyChangesTaskManager(cluster_db.id)
        self.assertRaises(errors.WrongNodeStatus, manager_.execute)

    @mock.patch('nailgun.task.manager.rpc.cast')
    def test_force_deploy_changes(self, mcast):
        self.env.create(
            nodes_kwargs=[
                {'status': NODE_STATUSES.ready},
                {'status': NODE_STATUSES.ready},
            ],
            cluster_kwargs={
                'status': consts.CLUSTER_STATUSES.operational
            },
            release_kwargs={
                'operating_system': consts.RELEASE_OS.ubuntu,
                'version': 'liberty-8.0'
            },
        )
        cluster_db = self.env.clusters[0]
        objects.Cluster.clear_pending_changes(cluster_db)
        manager_ = manager.ApplyChangesTaskManager(cluster_db.id)
        supertask = manager_.execute(force=True)
        self.assertEqual(supertask.name, TASK_NAMES.deploy)
        self.assertIn(supertask.status, TASK_STATUSES.pending)

        args, _ = mcast.call_args_list[0]
        deployment_info = args[1][0]['args']['deployment_info']
        self.assertItemsEqual(
            [node.uid for node in self.env.nodes],
            [node['uid'] for node in deployment_info]
        )

    @fake_tasks()
    @mock.patch('nailgun.task.manager.tasks.DeletionTask.execute')
    def test_apply_changes_exception_caught(self, mdeletion_execute):
        self.env.create(
            nodes_kwargs=[
                {"pending_deletion": True, "status": NODE_STATUSES.ready},
            ]
        )
        cluster_db = self.env.clusters[0]
        objects.Cluster.clear_pending_changes(cluster_db)
        manager_ = manager.ApplyChangesTaskManager(cluster_db.id)
        mdeletion_execute.side_effect = Exception('exception')
        task = manager_.execute()
        self.assertEqual(task.status, TASK_STATUSES.error)

    @fake_tasks(recover_offline_nodes=False)
    def test_deletion_offline_node(self):
        self.env.create(
            nodes_kwargs=[
                {"online": False, "pending_deletion": True},
                {"status": "ready"}
            ]
        )

        to_delete = TaskHelper.nodes_to_delete(self.env.clusters[0])
        to_delete_ids = [node.id for node in to_delete]
        self.assertEqual(len(to_delete_ids), 1)

        supertask = self.env.launch_deployment()
        self.assertEqual(supertask.status, consts.TASK_STATUSES.ready)

        self.assertEqual(self.env.db.query(models.Node).count(), 1)
        remaining_node = self.env.db.query(models.Node).first()
        self.assertNotIn(remaining_node.id, to_delete_ids)

    @fake_tasks(recover_offline_nodes=False, tick_interval=1)
    def test_deletion_three_offline_nodes_and_one_online(self):
        cluster = self.env.create(
            nodes_kwargs=[
                {"online": False, "pending_deletion": True},
                {"online": False, "pending_deletion": True},
                {"online": False, "pending_deletion": True},
                {"online": True, "pending_deletion": True}
            ]
        )

        supertask = self.env.launch_deployment()
        self.assertEqual(supertask.status, consts.TASK_STATUSES.ready)

        # Offline nodes were deleted, online node came back
        self.assertEqual(
            self.db.query(models.Node).filter(
                models.Node.cluster_id == cluster['id']).count(),
            0
        )
        self.assertEqual(
            self.db.query(models.Node).filter(
                models.Node.cluster_id.is_(None)).count(),
            1
        )
        self.assertEqual(
            self.db.query(models.Node).filter(
                models.Node.status == NODE_STATUSES.discover).count(),
            1
        )
        self.assertEqual(
            self.db.query(models.Node).filter(
                models.Node.online == sql.true()).count(),
            1
        )

    @fake_tasks(tick_interval=1)
    def test_delete_offile_nodes_and_recover_them(self):
        self.env.create(
            nodes_kwargs=[
                {"online": False, "pending_deletion": True},
                {"online": False, "pending_deletion": True},
                {"online": True, "pending_deletion": True}
            ]
        )

        supertask = self.env.launch_deployment()
        self.assertEqual(supertask.status, consts.TASK_STATUSES.ready)

        q_nodes = self.env.db.query(models.Node)

        online_nodes_count = q_nodes.filter_by(online=True).count()
        self.assertEqual(online_nodes_count, 1)

        offilne_nodes_count = q_nodes.filter_by(online=False).count()
        self.assertEqual(offilne_nodes_count, 2)

        for node in q_nodes:
            self.assertEqual(node.status, 'discover')
            self.assertEqual(node.cluster_id, None)

    @fake_tasks(recover_offline_nodes=False)
    def test_deletion_offline_node_when_cluster_has_only_one_node(self):
        cluster = self.env.create_cluster()
        objects.Cluster.clear_pending_changes(self.env.clusters[0])
        self.env.create_node(
            cluster_id=cluster['id'],
            online=False,
            pending_deletion=True,
            pending_addition=False,
            status='ready',
            roles=['controller'])

        supertask = self.env.launch_deployment()
        self.assertEqual(supertask.status, consts.TASK_STATUSES.ready)
        self.assertEqual(self.env.db.query(models.Node).count(), 0)

    @fake_tasks(recover_nodes=False)
    def test_node_deletion_task_manager(self):
        self.env.create(
            nodes_kwargs=[
                {"pending_deletion": True, "status": "ready"}
            ]
        )
        cluster_db = self.env.clusters[0]
        objects.Cluster.clear_pending_changes(cluster_db)
        manager_ = manager.NodeDeletionTaskManager(cluster_id=cluster_db.id)
        task = manager_.execute(cluster_db.nodes)
        self.assertEqual(task.status, consts.TASK_STATUSES.ready)

        # Synchronous run ensures that nodes are deleted.
        self.assertEqual(self.db.query(models.Node).count(), 0)

    @fake_tasks(recover_nodes=False)
    def test_node_deletion_task_mgr_works_for_nodes_not_in_cluster(self):
        self.env.create(
            nodes_kwargs=[
                {"pending_deletion": True, "status": "ready"}
            ]
        )
        cluster_db = self.env.clusters[0]
        objects.Cluster.clear_pending_changes(cluster_db)
        node = cluster_db.nodes[0]
        objects.Node.update(node, {'cluster_id': None})
        self.db.commit()

        manager_ = manager.NodeDeletionTaskManager()
        task = manager_.execute([node])
        self.assertEqual(task.status, TASK_STATUSES.ready)

        # Nodes are removed immediately
        self.assertEqual(self.db.query(models.Node).count(), 0)

    @fake_tasks(recover_nodes=False)
    def test_node_deletion_task_manager_invalid_cluster(self):
        self.env.create(
            nodes_kwargs=[
                {"pending_deletion": True, "status": "ready"}
            ]
        )
        cluster_db = self.env.clusters[0]
        objects.Cluster.clear_pending_changes(cluster_db)
        manager_ = manager.NodeDeletionTaskManager()

        self.assertRaises(
            errors.InvalidData, manager_.execute, cluster_db.nodes)

    @mock.patch('nailgun.task.manager.rpc.cast')
    def test_node_deletion_redeploy_started_for_proper_controllers(self,
                                                                   mcast):
        self.env.create(nodes_kwargs=[
            {'roles': ['controller'],
             'status': consts.NODE_STATUSES.provisioned},
            {'roles': ['controller'],
             'status': consts.NODE_STATUSES.discover},
        ])
        cluster_db = self.env.clusters[0]

        node_to_delete = self.env.create_node(
            cluster_id=cluster_db.id,
            roles=['controller'],
            status=consts.NODE_STATUSES.ready
        )
        node_to_deploy = self.env.create_node(
            cluster_id=cluster_db.id,
            roles=['controller'],
            status=consts.NODE_STATUSES.ready
        )

        manager_ = manager.NodeDeletionTaskManager(cluster_id=cluster_db.id)
        manager_.execute([node_to_delete])

        args, kwargs = mcast.call_args_list[0]
        depl_info = args[1][0]['args']['deployment_info']

        self.assertEqual(node_to_deploy.uid, depl_info[0]['uid'])

    def test_node_deletion_task_failed_with_controller_in_error(self):
        self.env.create(nodes_kwargs=[
            {'roles': ['controller'],
             'status': consts.NODE_STATUSES.error},
        ])
        cluster_db = self.env.clusters[0]

        node_to_delete = self.env.create_node(
            cluster_id=cluster_db.id,
            roles=['controller'],
            status=consts.NODE_STATUSES.ready
        )

        manager_ = manager.NodeDeletionTaskManager(cluster_id=cluster_db.id)
        self.assertRaises(errors.ControllerInErrorState,
                          manager_.execute, [node_to_delete])

    @fake_tasks()
    def test_deployment_on_controller_removal_via_apply_changes(self):
        self.env.create(
            nodes_kwargs=[
                {'roles': ['controller'],
                 'pending_deletion': True},
                {'roles': ['controller'],
                 'status': consts.NODE_STATUSES.ready},
                {'roles': ['controller'],
                 'status': consts.NODE_STATUSES.ready},
                {'roles': ['controller'],
                 'status': consts.NODE_STATUSES.ready},
                {'roles': ['compute'],
                 'status': consts.NODE_STATUSES.ready},
                {'roles': ['compute'],
                 'status': consts.NODE_STATUSES.ready},
            ]
        )

        cluster = self.env.clusters[0]
        expected_nodes_to_deploy = filter(lambda n: 'controller' in n.roles
                                                    and not n.pending_deletion,
                                          cluster.nodes)

        with mock.patch('nailgun.task.task.DeploymentTask.message') as \
                mocked_task:
            with mock.patch('nailgun.rpc.cast'):
                self.env.launch_deployment()
                _, actual_nodes_to_deploy = mocked_task.call_args[0]
                self.assertItemsEqual(expected_nodes_to_deploy,
                                      actual_nodes_to_deploy)

    @fake_tasks()
    def test_deployment_on_controller_removal_via_node_deletion(self):
        self.env.create(
            nodes_kwargs=[
                {'roles': ['controller'],
                 'status': consts.NODE_STATUSES.ready},
                {'roles': ['controller'],
                 'status': consts.NODE_STATUSES.ready},
                {'roles': ['controller'],
                 'status': consts.NODE_STATUSES.ready},
                {'roles': ['compute'],
                 'status': consts.NODE_STATUSES.ready},
                {'roles': ['compute'],
                 'status': consts.NODE_STATUSES.ready},
            ]
        )

        cluster = self.env.clusters[0]
        controllers = filter(lambda n: 'controller' in n.roles
                                       and not n.pending_deletion,
                             cluster.nodes)
        controller_to_delete = controllers[0]
        expected_nodes_to_deploy = controllers[1:]

        with mock.patch('nailgun.task.task.DeploymentTask.message') as \
                mocked_task:
            with mock.patch('nailgun.rpc.cast'):
                resp = self.app.delete(
                    reverse(
                        'NodeHandler',
                        kwargs={'obj_id': controller_to_delete.id}),
                    headers=self.default_headers
                )
                _, actual_nodes_to_deploy = mocked_task.call_args[0]
                self.assertItemsEqual(expected_nodes_to_deploy,
                                      actual_nodes_to_deploy)
                self.assertEqual(202, resp.status_code)

    @mock.patch('nailgun.rpc.cast')
    def test_delete_nodes_do_not_run_if_there_is_deletion_running(self, _):
        self.env.create(
            nodes_kwargs=[{'roles': ['controller']}] * 3)
        self.task_manager = manager.NodeDeletionTaskManager(
            cluster_id=self.env.clusters[0].id)

        self.task_manager.execute(self.env.nodes)
        self.assertRaisesRegexp(
            errors.DeploymentAlreadyStarted,
            'Cannot perform the actions because there are running tasks',
            self.task_manager.execute,
            self.env.nodes)

    @mock.patch('nailgun.rpc.cast')
    def test_delete_nodes_reelection_if_primary_for_deletion(self, _):
        self.env.create(
            nodes_kwargs=[{'roles': ['controller'],
                           'status': consts.NODE_STATUSES.ready}] * 3)
        cluster = self.env.clusters[0]
        task_manager = manager.NodeDeletionTaskManager(cluster_id=cluster.id)
        objects.Cluster.set_primary_roles(cluster, self.env.nodes)
        primary_node = filter(
            lambda n: 'controller' in n.primary_roles,
            self.env.nodes)[0]

        task_manager.execute([primary_node])
        self.env.refresh_nodes()

        new_primary = filter(
            lambda n: ('controller' in n.primary_roles and
                       n.pending_deletion is False),
            self.env.nodes)[0]

        self.assertNotEqual(primary_node.id, new_primary.id)

    @mock.patch('nailgun.task.task.rpc.cast')
    def test_node_group_deletion_failed_while_previous_in_progress(
            self, mocked_rpc
    ):
        self.env.create(
            cluster_kwargs={
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': consts.NEUTRON_SEGMENT_TYPES.gre},
            nodes_kwargs=[
                {'api': True,
                 'pending_addition': True}
            ]
        )
        ng1 = self.env.create_node_group(name='ng_1').json_body
        ng2 = self.env.create_node_group(name='ng_2').json_body
        self.assertEqual(mocked_rpc.call_count, 0)

        self.env.delete_node_group(ng1['id'])
        self.assertEqual(mocked_rpc.call_count, 1)
        # delete other node group
        # request should be rejected as previous update_dnsmasq task is still
        # in progress
        resp = self.env.delete_node_group(ng2['id'], status_code=409)
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.json_body['message'],
                         errors.UpdateDnsmasqTaskIsRunning.message)
        # no more calls were made
        self.assertEqual(mocked_rpc.call_count, 1)

    @mock.patch('nailgun.task.task.rpc.cast')
    def test_deployment_starts_if_nodes_not_changed(self, rpc_mock):
        self.env.create(
            release_kwargs={
                'operating_system': consts.RELEASE_OS.ubuntu,
                'version': 'mitaka-9.0'
            },
            nodes_kwargs=[
                {'status': NODE_STATUSES.ready, 'roles': ['controller']},
                {'status': NODE_STATUSES.ready, 'roles': ['compute']},
            ]
        )
        cluster = self.env.clusters[-1]
        supertask = self.env.launch_deployment(cluster.id)
        self.assertNotEqual(consts.TASK_STATUSES.error, supertask.status)
        tasks_graph = rpc_mock.call_args[0][1][0]['args']['tasks_graph']
        # check that nodes presents in tasks_graph
        self.assertItemsEqual(
            [n.uid for n in cluster.nodes] + [consts.MASTER_NODE_UID, None],
            tasks_graph
        )

    @mock.patch('nailgun.task.task.rpc.cast')
    @mock.patch('nailgun.objects.Cluster.get_deployment_tasks')
    def test_redeployment_ignore_conditions(self, tasks_mock, rpc_mock):
        tasks_mock.return_value = [
            {
                "id": "test", "roles": ['master'], "version": "2.0.1",
                "type": "puppet", "parameters": {},
                "condition": {"yaql_exp": "changed($.nodes)"}
            }
        ]
        self.env.create(
            release_kwargs={
                'operating_system': consts.RELEASE_OS.ubuntu,
                'version': 'mitaka-9.0'
            }
        )
        cluster = self.env.clusters[-1]
        # deploy cluster at first time
        supertask = self.env.launch_deployment(cluster.id)
        self.assertNotEqual(consts.TASK_STATUSES.error, supertask.status)
        self.env.set_task_status_recursively(
            supertask, consts.TASK_STATUSES.ready
        )
        self.set_history_ready()
        self.db.flush()
        tasks_graph = rpc_mock.call_args[0][1][0]['args']['tasks_graph']
        self.assertEqual('puppet', tasks_graph['master'][0]['type'])

        # launch cluster deployment again, because there is no changes
        # the task should be skipped
        supertask = self.env.launch_deployment(cluster.id)
        self.assertNotEqual(consts.TASK_STATUSES.error, supertask.status)
        self.env.set_task_status_recursively(
            supertask, consts.TASK_STATUSES.ready
        )
        self.db.flush()
        tasks_graph = rpc_mock.call_args[0][1][0]['args']['tasks_graph']
        self.assertEqual('skipped', tasks_graph['master'][0]['type'])
        supertask.status = consts.TASK_STATUSES.ready
        self.set_history_ready()
        self.db.flush()

        # force cluster re-deployment, the task should not be skipped
        supertask = self.env.launch_redeployment(cluster.id)
        self.assertNotEqual(consts.TASK_STATUSES.error, supertask.status)
        tasks_graph = rpc_mock.call_args[0][1][0]['args']['tasks_graph']
        self.assertEqual('puppet', tasks_graph['master'][0]['type'])

    @mock.patch('nailgun.rpc.cast')
    def test_deploy_part_of_pending_addition_nodes(self, rpc_mock):
        self.env.create(
            release_kwargs={
                'operating_system': consts.RELEASE_OS.ubuntu,
                'version': 'mitaka-9.0'
            },
            nodes_kwargs=[
                {'status': NODE_STATUSES.provisioned, 'roles': ['controller']},
                {'status': NODE_STATUSES.provisioned, 'roles': ['compute']},
            ]
        )
        cluster = self.env.clusters[-1]
        nodes_uids = [n.uid for n in cluster.nodes]
        node3 = self.env.create_node(
            api=False, cluster_id=cluster.id,
            roles=["compute"],
            pending_addition=True
        )
        t = self.env.launch_deployment_selected(nodes_uids, cluster.id)
        self.assertNotEqual(consts.TASK_STATUSES.error, t.status)
        self.db.refresh(node3)
        self.assertEqual(consts.NODE_STATUSES.discover, node3.status)
        self.assertTrue(node3.pending_addition)
        tasks_graph = rpc_mock.call_args[0][1]['args']['tasks_graph']
        self.assertItemsEqual(
            [consts.MASTER_NODE_UID, None] + nodes_uids, tasks_graph
        )

    @mock.patch('nailgun.task.task.rpc.cast')
    @mock.patch('nailgun.objects.Cluster.get_deployment_tasks')
    def test_only_certain_tasks_run_in_deploy(self, tasks_mock, rpc_mock):
        task = {
            'id': 'test', 'parameters': {}, 'type': 'puppet',
            'roles': ['master'], 'version': '2.1.0',
        }

        tasks = []
        for i in range(5):
            task_copy = task.copy()
            task_copy['id'] = 'test' + str(i)
            tasks.append(task_copy)

        tasks_mock.return_value = tasks

        cluster = self.env.create(
            nodes_kwargs=[
                {'status': NODE_STATUSES.provisioned, 'roles': ['controller']},
                {'status': NODE_STATUSES.provisioned, 'roles': ['compute']},
                {'status': NODE_STATUSES.provisioned, 'roles': ['cinder']},
            ],
            release_kwargs={
                'operating_system': consts.RELEASE_OS.ubuntu,
                'version': 'mitaka-9.0',
            },
        )
        task_ids = ['test0', 'test3']
        task = self.env.launch_deployment_selected_tasks(
            [n.uid for n in cluster.nodes],
            cluster.id, task_ids)

        self.assertNotEqual(consts.TASK_STATUSES.error, task.status)

        tasks_graph = rpc_mock.call_args[0][1]['args']['tasks_graph']
        for task in tasks_graph['master']:
            if task['id'] in task_ids:
                self.assertEqual(task['type'], 'puppet')
            else:
                self.assertEqual(task['type'], 'skipped')

    @mock.patch('nailgun.rpc.cast')
    def test_deployment_task_uses_all_nodes_by_default(self, rpc_mock):
        cluster = self.env.create(
            release_kwargs={
                'operating_system': consts.RELEASE_OS.ubuntu,
                'version': 'mitaka-9.0'
            },
            nodes_kwargs=[{'roles': ['controller'],
                           'status': consts.NODE_STATUSES.ready}] * 3
        )
        resp = self.app.put(
            reverse(
                'DeploySelectedNodes',
                kwargs={'cluster_id': cluster.id}
            ),
            '{}',
            headers=self.default_headers
        )
        self.assertIn(resp.status_code, [200, 202])
        tasks_graph = rpc_mock.call_args[0][1]['args']['tasks_graph']
        # check that all nodes present in message
        self.assertItemsEqual(
            [n.uid for n in cluster.nodes] + [consts.MASTER_NODE_UID, None],
            tasks_graph
        )

    @mock.patch('nailgun.task.task.rpc.cast')
    @mock.patch('nailgun.objects.Cluster.get_deployment_tasks')
    def test_correct_state_calculation(self, tasks_mock, rpc_mock):
        cluster = self.env.create(
            nodes_kwargs=[{'roles': ['controller'],
                           'status': consts.NODE_STATUSES.provisioned}],
            release_kwargs={
                'operating_system': consts.RELEASE_OS.ubuntu,
                'version': 'mitaka-9.0'
            }
        )
        node = cluster.nodes[0]

        task = {
            'parameters': {}, 'type': 'puppet',
            'roles': ['master'], 'version': '2.1.0',
            'condition': {'yaql_exp': 'changed($)'},
        }

        tasks_mock.return_value = [
            dict(task, id='test1'), dict(task, id='test2')
        ]

        # deploy cluster at first time and create history
        supertask = self.env.launch_deployment_selected([node.uid], cluster.id)
        self.assertNotEqual(consts.TASK_STATUSES.error, supertask.status)

        self.set_history_ready()

        # mock get_last_succeeded_transactions in such way that it
        # contains only information about test1 task
        mocked = (
            'objects.TransactionCollection.get_last_succeeded_transactions'
        )
        with mock.patch(mocked, return_value=[(supertask, 'test1')]):
            task = self.env.launch_deployment_selected([node.uid], cluster.id)
            self.assertNotEqual(consts.TASK_STATUSES.error, task.status)
            tasks_graph = rpc_mock.call_args[0][1]['args']['tasks_graph']

            # chek that test1 task skipped by condition and test2 was not
            for task in tasks_graph['master']:
                if task['id'] == 'test1':
                    self.assertEqual(
                        task['type'], consts.ORCHESTRATOR_TASK_TYPES.skipped)
                elif task['id'] == 'test2':
                    self.assertNotEqual(
                        task['type'], consts.ORCHESTRATOR_TASK_TYPES.skipped)


class TestUpdateDnsmasqTaskManagers(BaseIntegrationTest):

    def setUp(self):
        super(TestUpdateDnsmasqTaskManagers, self).setUp()
        cluster = self.env.create(
            cluster_kwargs={
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': consts.NEUTRON_SEGMENT_TYPES.gre},
            nodes_kwargs=[
                {'api': True,
                 'pending_addition': True}
            ]
        )
        self.cluster = self.db.query(models.Cluster).get(cluster['id'])

    def change_ip_range(self, net_name='fuelweb_admin', status_code=200):
        data = self.env.neutron_networks_get(self.cluster['id']).json_body
        admin = filter(lambda ng: ng['name'] == net_name,
                       data['networks'])[0]

        orig_range = netaddr.IPRange(admin['ip_ranges'][0][0],
                                     admin['ip_ranges'][0][1])
        admin['ip_ranges'][0] = [str(orig_range[0]), str(orig_range[-2])]

        resp = self.env.neutron_networks_put(
            self.cluster['id'], data, expect_errors=(status_code != 200))
        self.assertEqual(resp.status_code, status_code)
        return resp

    def test_update_dnsmasq_is_started_with_correct_message(self):
        message = {
            'api_version': '1',
            'method': 'execute_tasks',
            'respond_to': 'update_dnsmasq_resp',
            'args': {
                'task_uuid': '',
                'tasks': [{
                    'type': consts.ORCHESTRATOR_TASK_TYPES.upload_file,
                    'uids': ['master'],
                    'parameters': {
                        'path': '/etc/hiera/networks.yaml',
                        'data': ''}
                }, {
                    'type': consts.ORCHESTRATOR_TASK_TYPES.puppet,
                    'uids': ['master'],
                    'parameters': {
                        'puppet_modules': '/etc/puppet/modules',
                        'puppet_manifest': '/etc/puppet/modules/fuel/'
                                           'examples/dhcp-ranges.pp',
                        'timeout': 300,
                        'cwd': '/'}
                }, {
                    'type': 'cobbler_sync',
                    'uids': ['master'],
                    'parameters': {
                        'provisioning_info': {
                            'engine': {
                                'url': 'http://localhost/cobbler_api',
                                'username': 'cobbler',
                                'password': 'cobbler',
                                'master_ip': '127.0.0.1'
                            }
                        }
                    }
                }]
            }
        }

        with mock.patch('nailgun.task.task.rpc.cast') as \
                mocked_task:
            self.change_ip_range()

            message['args']['tasks'][0]['parameters']['data'] = yaml.safe_dump(
                task.UpdateDnsmasqTask.get_admin_networks_data())
            update_task = self.db.query(models.Task).filter_by(
                name=consts.TASK_NAMES.update_dnsmasq).first()
            message['args']['task_uuid'] = update_task.uuid

            self.assertEqual(mocked_task.call_count, 1)
            self.assertEqual(mocked_task.call_args[0][1], message)

    @mock.patch('nailgun.task.task.rpc.cast')
    def test_update_dnsmasq_started_and_completed(self, mocked_rpc):
        self.change_ip_range()
        self.assertEqual(mocked_rpc.call_count, 1)
        update_task = self.db.query(models.Task).filter_by(
            name=consts.TASK_NAMES.update_dnsmasq).first()
        self.assertEqual(update_task.status, consts.TASK_STATUSES.running)

        update_dnsmasq_msg = {
            "status": "ready",
            "task_uuid": update_task.uuid,
            "error": "",
            "msg": "Everything went fine."}

        rpc.receiver.NailgunReceiver.update_dnsmasq_resp(**update_dnsmasq_msg)
        self.db.refresh(update_task)
        self.assertEqual(update_task.status, consts.TASK_STATUSES.ready)
        self.assertEqual(update_task.message, update_dnsmasq_msg['msg'])
        self.assertIsNone(update_task.deleted_at)

        # run it one more time
        self.change_ip_range()
        # rpc.cast was called one more time
        self.assertEqual(mocked_rpc.call_count, 2)
        update_tasks = self.db.query(models.Task).filter_by(
            name=consts.TASK_NAMES.update_dnsmasq)
        new_tasks = update_tasks.filter_by(status=consts.TASK_STATUSES.running)
        self.assertEqual(new_tasks.count(), 1)
        # old task was marked as deleted
        self.assertEqual(update_tasks.count(), 2)
        self.db.refresh(update_task)
        self.assertIsNotNone(update_task.deleted_at)

    @mock.patch('nailgun.task.task.rpc.cast')
    def test_update_dnsmasq_started_and_failed(self, mocked_rpc):
        self.change_ip_range()
        self.assertEqual(mocked_rpc.call_count, 1)
        update_task = self.db.query(models.Task).filter_by(
            name=consts.TASK_NAMES.update_dnsmasq).first()
        self.assertEqual(update_task.status, consts.TASK_STATUSES.running)

        update_dnsmasq_msg = {
            "status": consts.TASK_STATUSES.error,
            "task_uuid": update_task.uuid,
            "error": "Something went wrong.",
            "msg": ""}

        rpc.receiver.NailgunReceiver.update_dnsmasq_resp(**update_dnsmasq_msg)
        self.db.refresh(update_task)
        self.assertEqual(update_task.status, consts.TASK_STATUSES.error)
        self.assertEqual(update_task.message, update_dnsmasq_msg['error'])
        self.assertIsNone(update_task.deleted_at)

        # run it one more time
        self.change_ip_range()
        # rpc.cast was called one more time
        self.assertEqual(mocked_rpc.call_count, 2)
        update_tasks = self.db.query(models.Task).filter_by(
            name=consts.TASK_NAMES.update_dnsmasq)
        new_tasks = update_tasks.filter_by(status=consts.TASK_STATUSES.running)
        self.assertEqual(new_tasks.count(), 1)
        # old task was marked as deleted
        self.assertEqual(update_tasks.count(), 2)
        self.db.refresh(update_task)
        self.assertIsNotNone(update_task.deleted_at)

    @mock.patch('nailgun.task.task.rpc.cast')
    def test_update_admin_failed_while_previous_in_progress(self, mocked_rpc):
        self.change_ip_range()
        self.assertEqual(mocked_rpc.call_count, 1)
        update_task = self.db.query(models.Task).filter_by(
            name=consts.TASK_NAMES.update_dnsmasq).first()
        self.assertEqual(update_task.status, consts.TASK_STATUSES.running)

        # change of other network works as it does not require to run
        # update_dnsmasq
        self.change_ip_range(net_name='public')
        # no more calls were made
        self.assertEqual(mocked_rpc.call_count, 1)

        # request was rejected as previous update_dnsmasq task is still
        # in progress
        resp = self.change_ip_range(status_code=409)
        self.assertEqual(resp.json_body['message'],
                         errors.UpdateDnsmasqTaskIsRunning.message)
        # no more calls were made
        self.assertEqual(mocked_rpc.call_count, 1)

    @mock.patch('nailgun.task.task.rpc.cast')
    def test_update_dnsmasq_started_on_node_group_deletion(self, mocked_rpc):
        ng = self.env.create_node_group().json_body
        self.assertEqual(mocked_rpc.call_count, 0)

        self.env.delete_node_group(ng['id'])
        self.assertEqual(mocked_rpc.call_count, 1)
        update_task = self.db.query(models.Task).filter_by(
            name=consts.TASK_NAMES.update_dnsmasq).first()
        self.assertEqual(update_task.status, consts.TASK_STATUSES.running)
