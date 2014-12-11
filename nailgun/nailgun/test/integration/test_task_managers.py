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
import nailgun.rpc as rpc
import time

from mock import patch

from nailgun import objects

from nailgun.consts import ACTION_TYPES
from nailgun.consts import NODE_STATUSES
from nailgun.consts import TASK_NAMES
from nailgun.consts import TASK_STATUSES
from nailgun.settings import settings

from nailgun.db.sqlalchemy.models import Cluster
from nailgun.db.sqlalchemy.models import Node
from nailgun.db.sqlalchemy.models import Notification
from nailgun.db.sqlalchemy.models import Task
from nailgun.errors import errors
from nailgun.task.manager import ApplyChangesTaskManager
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks
from nailgun.test.base import reverse


class TestTaskManagers(BaseIntegrationTest):

    def tearDown(self):
        self._wait_for_threads()
        super(TestTaskManagers, self).tearDown()

    def check_node_presence(self, nodes_count):
        return self.db.query(Node).count() == nodes_count

    @fake_tasks(godmode=True)
    def test_deployment_task_managers(self):
        self.env.create(
            nodes_kwargs=[
                {"pending_addition": True},
                {"pending_deletion": True,
                 'status': NODE_STATUSES.provisioned},
            ]
        )
        supertask = self.env.launch_deployment()
        self.env.refresh_nodes()
        self.assertEqual(supertask.name, TASK_NAMES.deploy)
        self.assertIn(
            supertask.status,
            (TASK_STATUSES.running, TASK_STATUSES.ready)
        )
        # we have three subtasks here
        # deletion
        # provision
        # deployment
        self.assertEqual(len(supertask.subtasks), 3)
        # provisioning task has less weight then deployment
        provision_task = filter(
            lambda t: t.name == TASK_NAMES.provision, supertask.subtasks)[0]
        self.assertEqual(provision_task.weight, 0.4)

        wait_nodes = [self.env.nodes[0]]
        self.env.wait_for_nodes_status(wait_nodes, NODE_STATUSES.provisioning)
        self.env.wait_ready(
            supertask,
            60,
            u"Successfully removed 1 node(s). No errors occurred; "
            "Deployment of environment '{0}' is done".format(
                self.env.clusters[0].name
            )
        )
        self.env.wait_for_nodes_status(wait_nodes, NODE_STATUSES.ready)
        self.env.refresh_nodes()
        for n in filter(
            lambda n: n.cluster_id == self.env.clusters[0].id,
            self.env.nodes
        ):
            self.assertEqual(n.status, NODE_STATUSES.ready)
            self.assertEqual(n.progress, 100)

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
            action_log = objects.ActionLog.get_by_task_uuid(subtask.uuid)

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

    def test_check_before_deployment_with_error(self):
        self.env.create(
            nodes_kwargs=[
                {"pending_addition": True, "online": False}
            ]
        )

        supertask = self.env.launch_deployment()

        action_logs = objects.ActionLogCollection.all()

        self.assertEqual(action_logs.count(), 3)
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
    @patch('nailgun.rpc.cast')
    def test_do_not_send_node_to_orchestrator_which_has_status_discover(
            self, _):

        self.env.create(
            nodes_kwargs=[
                {'pending_deletion': True, 'status': 'discover'}])

        self.env.launch_deployment()

        args, kwargs = nailgun.task.manager.rpc.cast.call_args
        self.assertEqual(len(args[1]['args']['nodes']), 0)

        self.env.refresh_nodes()
        for n in self.env.nodes:
            self.assertEqual(len(self.env.nodes), 0)

    @fake_tasks(fake_rpc=False, mock_rpc=False)
    @patch('nailgun.rpc.cast')
    def test_send_to_orchestrator_offline_nodes(self, _):
        self.env.create(
            nodes_kwargs=[
                {'pending_deletion': True,
                 'status': 'ready',
                 'online': False}])

        self.env.launch_deployment()

        args, kwargs = nailgun.task.manager.rpc.cast.call_args
        self.assertEqual(len(args[1]['args']['nodes']), 1)

    @fake_tasks()
    def test_do_not_redeploy_nodes_in_ready_status(self):
        self.env.create(nodes_kwargs=[
            {"pending_addition": True},
            {"pending_addition": True, 'roles': ['compute']}])
        cluster_db = self.env.clusters[0]
        # Generate ips, fqdns
        objects.NodeCollection.prepare_for_deployment(cluster_db.nodes)
        # First node with status ready
        # should not be readeployed
        self.env.nodes[0].status = 'ready'
        self.env.nodes[0].pending_addition = False
        self.db.commit()

        objects.Cluster.clear_pending_changes(cluster_db)

        supertask = self.env.launch_deployment()
        self.assertEqual(supertask.name, 'deploy')
        self.assertIn(supertask.status, ('running', 'ready'))

        self.assertEqual(self.env.nodes[0].status, 'ready')
        self.env.wait_for_nodes_status([self.env.nodes[1]], 'provisioning')
        self.env.wait_ready(supertask)

        self.env.refresh_nodes()

        self.assertEqual(self.env.nodes[1].status, 'ready')
        self.assertEqual(self.env.nodes[1].progress, 100)

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
        self.env.wait_error(
            supertask,
            5,
            'Nodes "{0}" are offline. Remove them from environment '
            'and try again.'.format(offline_node.full_name)
        )
        # Do not move cluster to error state
        # in case if cluster new and before
        # validation failed
        self.assertEqual(self.env.clusters[0].status, 'new')

    @fake_tasks(godmode=True)
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
        self.env.wait_ready(supertask, 60)
        self.env.refresh_nodes()

        self.env.create_node(
            cluster_id=self.env.clusters[0].id,
            roles=["controller"],
            pending_addition=True
        )

        supertask = self.env.launch_deployment()
        self.env.wait_ready(supertask, 60)
        self.env.refresh_nodes()
        for n in self.env.nodes:
            self.assertEqual(n.status, 'ready')
            self.assertEqual(n.progress, 100)

    def test_deletion_empty_cluster_task_manager(self):
        cluster = self.env.create_cluster(api=True)
        resp = self.app.delete(
            reverse(
                'ClusterHandler',
                kwargs={'obj_id': self.env.clusters[0].id}),
            headers=self.default_headers
        )
        self.assertEqual(202, resp.status_code)

        timer = time.time()
        timeout = 15
        clstr = self.db.query(Cluster).get(self.env.clusters[0].id)
        while clstr:
            time.sleep(1)
            try:
                self.db.refresh(clstr)
            except Exception:
                break
            if time.time() - timer > timeout:
                raise Exception("Cluster deletion seems to be hanged")

        notification = self.db.query(Notification)\
            .filter(Notification.topic == "done")\
            .filter(Notification.message == "Environment '%s' and all its "
                    "nodes are deleted" % cluster["name"]).first()
        self.assertIsNotNone(notification)

        tasks = self.db.query(Task).all()
        self.assertEqual(tasks, [])

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

        timer = time.time()
        timeout = 15
        clstr = self.db.query(Cluster).get(cluster_id)
        while clstr:
            time.sleep(1)
            try:
                self.db.refresh(clstr)
            except Exception:
                break
            if time.time() - timer > timeout:
                raise Exception("Cluster deletion seems to be hanged")

        notification = self.db.query(Notification)\
            .filter(Notification.topic == "done")\
            .filter(Notification.message == "Environment '%s' and all its "
                    "nodes are deleted" % cluster_name).first()
        self.assertIsNotNone(notification)

        tasks = self.db.query(Task).all()
        self.assertEqual(tasks, [])

    @fake_tasks(recover_nodes=False)
    def test_deletion_during_deployment(self):
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
        self.app.delete(
            reverse(
                'ClusterHandler',
                kwargs={'obj_id': cluster_id}),
            headers=self.default_headers
        )

        def cluster_is_deleted():
            return not self.db.query(Cluster).get(cluster_id)

        self.env.wait_for_true(cluster_is_deleted,
                               error_message="Cluster deletion timeout")

        task_deploy = self.db.query(Task).filter_by(
            uuid=deploy_uuid
        ).first()
        self.assertIsNone(task_deploy)
        task_delete = self.db.query(Task).filter_by(
            cluster_id=cluster_id,
            name="cluster_deletion"
        ).first()
        self.assertIsNone(task_delete)

    @fake_tasks(godmode=True)
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
        self.env.wait_ready(supertask)

        resp = self.app.delete(
            reverse(
                'ClusterHandler',
                kwargs={'obj_id': cluster_id}),
            headers=self.default_headers
        )
        self.assertEqual(202, resp.status_code)

        timer = time.time()
        timeout = 15
        clstr = self.db.query(Cluster).get(cluster_id)
        while clstr:
            time.sleep(1)
            try:
                self.db.refresh(clstr)
            except Exception:
                break
            if time.time() - timer > timeout:
                raise Exception("Cluster deletion seems to be hanged")

        notification = self.db.query(Notification)\
            .filter(Notification.topic == "done")\
            .filter(Notification.message == "Environment '%s' and all its "
                    "nodes are deleted" % cluster_name).first()
        self.assertIsNotNone(notification)

        tasks = self.db.query(Task).all()
        self.assertEqual(tasks, [])

    @fake_tasks()
    def test_node_fqdn_is_assigned(self):
        self.env.create(
            nodes_kwargs=[
                {"pending_addition": True},
                {"pending_addition": True}
            ]
        )
        self.env.launch_deployment()
        self.env.refresh_nodes()
        for node in self.env.nodes:
            fqdn = "node-%s.%s" % (node.id, settings.DNS_DOMAIN)
            self.assertEqual(fqdn, node.fqdn)

    @fake_tasks()
    def test_no_node_no_cry(self):
        cluster = self.env.create_cluster(api=True)
        cluster_id = cluster['id']
        manager = ApplyChangesTaskManager(cluster_id)
        task = Task(name='provision', cluster_id=cluster_id)
        self.db.add(task)
        self.db.commit()
        rpc.receiver.NailgunReceiver.deploy_resp(nodes=[
            {'uid': 666, 'id': 666, 'status': 'discover'}
        ], task_uuid=task.uuid)
        self.assertRaises(errors.WrongNodeStatus, manager.execute)

    @fake_tasks()
    def test_no_changes_no_cry(self):
        self.env.create(
            nodes_kwargs=[
                {"status": "ready"}
            ]
        )
        cluster_db = self.env.clusters[0]
        objects.Cluster.clear_pending_changes(cluster_db)
        manager = ApplyChangesTaskManager(cluster_db.id)
        self.assertRaises(errors.WrongNodeStatus, manager.execute)

    @fake_tasks(recover_offline_nodes=False)
    def test_deletion_offline_node(self):
        self.env.create(
            nodes_kwargs=[
                {"online": False, "pending_deletion": True},
                {"status": "ready"}
            ]
        )

        supertask = self.env.launch_deployment()
        self.env.wait_ready(supertask, timeout=5)
        self.assertEqual(self.env.db.query(Node).count(), 1)

    @fake_tasks(recover_offline_nodes=False, tick_interval=1)
    def test_deletion_three_offline_nodes_and_one_online(self):
        self.env.create(
            nodes_kwargs=[
                {"online": False, "pending_deletion": True},
                {"online": False, "pending_deletion": True},
                {"online": False, "pending_deletion": True},
                {"online": True, "pending_deletion": True}
            ]
        )

        supertask = self.env.launch_deployment()
        self.db.flush()
        self.env.wait_ready(supertask, timeout=5)

        # this test is failing when whole test set is executing
        # apparently the main reason for that is delays in data
        # updating inside of fake threads so in order to make test
        # pass we have to wait for data to be present in db
        self.env.wait_for_true(self.check_node_presence, args=[1])

        node = self.db.query(Node).first()
        self.assertEqual(node.status, 'discover')
        self.assertEqual(node.cluster_id, None)

    @fake_tasks(recover_nodes=True, recover_offline_nodes=True,
                tick_interval=1)
    def test_delete_offile_nodes_and_recover_them(self):
        self.env.create(
            nodes_kwargs=[
                {"online": False, "pending_deletion": True},
                {"online": False, "pending_deletion": True},
                {"online": True, "pending_deletion": True}
            ]
        )

        supertask = self.env.launch_deployment()
        self.db.flush()
        self.env.wait_ready(supertask, timeout=5)

        # same as in previous test
        self.env.wait_for_true(self.check_node_presence, args=[3])

        q_nodes = self.env.db.query(Node)

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
        self.env.wait_ready(supertask, timeout=5)
        self.assertEqual(self.env.db.query(Node).count(), 0)
