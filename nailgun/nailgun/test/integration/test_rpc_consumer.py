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

import datetime
import random
import uuid

from nailgun.db.sqlalchemy.models import Attributes
from nailgun.db.sqlalchemy.models import Cluster
from nailgun.db.sqlalchemy.models import IPAddr
from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun.db.sqlalchemy.models import Node
from nailgun.db.sqlalchemy.models import Notification
from nailgun.db.sqlalchemy.models import Task
from nailgun.rpc import receiver as rcvr
from nailgun.settings import settings
from nailgun.task import helpers
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import reverse

from nailgun import consts

from nailgun import objects


class TestVerifyNetworks(BaseIntegrationTest):

    def setUp(self):
        super(TestVerifyNetworks, self).setUp()
        self.receiver = rcvr.NailgunReceiver()

    def test_verify_networks_resp(self):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"api": False},
                {"api": False}
            ]
        )
        cluster_db = self.env.clusters[0]
        node1, node2 = self.env.nodes
        nets = [{'iface': 'eth0', 'vlans': range(100, 105)}]

        task = Task(
            name="verify_networks",
            cluster_id=cluster_db.id
        )
        task.cache = {
            "args": {
                "nodes": [{'uid': node1.id, 'networks': nets},
                          {'uid': node2.id, 'networks': nets}]
            }
        }
        self.db.add(task)
        self.db.commit()

        kwargs = {'task_uuid': task.uuid,
                  'status': 'ready',
                  'nodes': [{'uid': node1.id, 'networks': nets},
                            {'uid': node2.id, 'networks': nets}]}
        self.receiver.verify_networks_resp(**kwargs)
        self.db.flush()
        self.db.refresh(task)
        self.assertEqual(task.status, "ready")
        self.assertEqual(task.message, '')

    def test_verify_networks_resp_error(self):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"api": False},
                {"api": False}
            ]
        )
        cluster_db = self.env.clusters[0]
        node1, node2 = self.env.nodes
        nets_sent = [{'iface': 'eth0', 'vlans': range(100, 105)}]
        nets_resp = [{'iface': 'eth0', 'vlans': range(100, 104)}]

        task = Task(
            name="super",
            cluster_id=cluster_db.id
        )
        task.cache = {
            "args": {
                'nodes': [{'uid': node1.id, 'networks': nets_sent},
                          {'uid': node2.id, 'networks': nets_sent}]
            }
        }
        self.db.add(task)
        self.db.commit()

        kwargs = {'task_uuid': task.uuid,
                  'status': 'ready',
                  'nodes': [{'uid': node1.id, 'networks': nets_resp},
                            {'uid': node2.id, 'networks': nets_resp}]}
        self.receiver.verify_networks_resp(**kwargs)
        self.db.flush()
        self.db.refresh(task)
        self.assertEqual(task.status, "error")
        error_nodes = []
        for node in self.env.nodes:
            error_nodes.append({'uid': node.id, 'interface': 'eth0',
                                'name': node.name, 'absent_vlans': [104],
                                'mac': node.interfaces[0].mac})
        self.assertEqual(task.message, '')
        self.assertEqual(task.result, error_nodes)

    def test_verify_networks_resp_error_with_removed_node(self):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"api": False},
                {"api": False}
            ]
        )

        cluster_db = self.env.clusters[0]
        node1, node2 = self.env.nodes
        nets_sent = [{'iface': 'eth0', 'vlans': range(100, 105)}]
        nets_resp = [{'iface': 'eth0', 'vlans': range(100, 104)}]

        task = Task(
            name="super",
            cluster_id=cluster_db.id
        )
        task.cache = {
            "args": {
                'nodes': [{'uid': node1.id, 'networks': nets_sent},
                          {'uid': node2.id, 'networks': nets_sent}]
            }
        }
        self.db.add(task)
        self.db.commit()

        kwargs = {'task_uuid': task.uuid,
                  'status': 'ready',
                  'nodes': [{'uid': node1.id, 'networks': nets_resp},
                            {'uid': node2.id, 'networks': nets_resp}]}
        self.db.delete(node2)
        self.db.commit()
        self.receiver.verify_networks_resp(**kwargs)
        self.db.flush()
        resp = self.app.get(
            reverse('TaskHandler', kwargs={'obj_id': task.id}),
            headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 200)
        task = resp.json_body
        self.assertEqual(task['status'], "error")
        error_nodes = [{'uid': node1.id, 'interface': 'eth0',
                        'name': node1.name, 'absent_vlans': [104],
                        'mac': node1.interfaces[0].mac},
                       {'uid': node2.id, 'interface': 'eth0',
                        'absent_vlans': [104]}]
        self.assertEqual(task.get('message'), '')
        self.assertEqual(task['result'], error_nodes)

    def test_verify_networks_resp_empty_nodes_custom_error(self):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"api": False},
                {"api": False}
            ]
        )
        cluster_db = self.env.clusters[0]
        node1, node2 = self.env.nodes
        nets_sent = [{'iface': 'eth0', 'vlans': range(100, 105)}]

        task = Task(
            name="super",
            cluster_id=cluster_db.id
        )
        task.cache = {
            "args": {
                'nodes': [{'uid': node1.id, 'networks': nets_sent},
                          {'uid': node2.id, 'networks': nets_sent}]
            }
        }
        self.db.add(task)
        self.db.commit()

        error_msg = 'Custom error message.'
        kwargs = {'task_uuid': task.uuid,
                  'status': 'ready',
                  'nodes': [],
                  'error': error_msg}
        self.receiver.verify_networks_resp(**kwargs)
        self.db.flush()
        self.db.refresh(task)
        self.assertEqual(task.status, "error")
        self.assertEqual(task.message, error_msg)

    def test_verify_networks_resp_extra_nodes_error(self):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"api": False},
                {"api": False}
            ]
        )
        cluster_db = self.env.clusters[0]
        node1, node2 = self.env.nodes
        node3 = self.env.create_node(api=False)
        nets_sent = [{'iface': 'eth0', 'vlans': range(100, 105)}]

        task = Task(
            name="super",
            cluster_id=cluster_db.id
        )
        task.cache = {
            "args": {
                'nodes': [{'uid': node1.id, 'networks': nets_sent},
                          {'uid': node2.id, 'networks': nets_sent}]
            }
        }
        self.db.add(task)
        self.db.commit()

        kwargs = {'task_uuid': task.uuid,
                  'status': 'ready',
                  'nodes': [{'uid': node3.id, 'networks': nets_sent},
                            {'uid': node2.id, 'networks': nets_sent},
                            {'uid': node1.id, 'networks': nets_sent}]}
        self.receiver.verify_networks_resp(**kwargs)
        self.db.flush()
        self.db.refresh(task)
        self.assertEqual(task.status, "ready")
        self.assertEqual(task.message, '')

    def test_verify_networks_with_dhcp_subtask(self):
        """Test verifies that when dhcp subtask is ready and
        verify_networks errored - verify_networks will be in error
        """
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"api": False},
                {"api": False}
            ]
        )
        cluster_db = self.env.clusters[0]
        node1, node2 = self.env.nodes
        nets_sent = [{'iface': 'eth0', 'vlans': range(100, 105)}]

        task = Task(
            name="verify_networks",
            cluster_id=cluster_db.id
        )
        task.cache = {
            "args": {
                'nodes': [{'uid': node1.id, 'networks': nets_sent},
                          {'uid': node2.id, 'networks': nets_sent}]
            }
        }
        self.db.add(task)
        self.db.commit()
        dhcp_subtask = Task(
            name='check_dhcp',
            cluster_id=cluster_db.id,
            parent_id=task.id,
            status='ready'
        )
        self.db.add(dhcp_subtask)
        self.db.commit()
        kwargs = {'task_uuid': task.uuid,
                  'status': 'ready',
                  'nodes': [{'uid': node1.id, 'networks': nets_sent},
                            {'uid': node2.id, 'networks': []}]}
        self.receiver.verify_networks_resp(**kwargs)
        self.assertEqual(task.status, "error")

    def test_verify_networks_with_dhcp_subtask_erred(self):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"api": False},
                {"api": False}
            ]
        )
        cluster_db = self.env.clusters[0]
        node1, node2 = self.env.nodes
        nets_sent = [{'iface': 'eth0', 'vlans': range(100, 105)}]

        task = Task(
            name="verify_networks",
            cluster_id=cluster_db.id
        )
        task.cache = {
            "args": {
                'nodes': [{'uid': node1.id, 'networks': nets_sent},
                          {'uid': node2.id, 'networks': nets_sent}]
            }
        }
        self.db.add(task)
        self.db.commit()
        dhcp_subtask = Task(
            name='check_dhcp',
            cluster_id=cluster_db.id,
            parent_id=task.id,
            status='error',
            message='DHCP ERROR'
        )
        self.db.add(dhcp_subtask)
        self.db.commit()
        kwargs = {'task_uuid': task.uuid,
                  'status': 'ready',
                  'nodes': [{'uid': node1.id, 'networks': nets_sent},
                            {'uid': node2.id, 'networks': []}]}
        self.receiver.verify_networks_resp(**kwargs)

        self.assertEqual(task.status, "error")
        self.assertEqual(task.message, u'DHCP ERROR')
        self.assertEqual(task.result, [{
            u'absent_vlans': [100, 101, 102, 103, 104],
            u'interface': 'eth0',
            u'mac': node2.interfaces[0].mac,
            u'name': 'Untitled ({0})'.format(node2.mac[-5:].lower()),
            u'uid': node2.id}])

    def test_verify_networks_resp_forgotten_node_error(self):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"api": False, 'name': 'node1'},
                {"api": False, 'name': 'node2'},
                {"api": False, 'name': 'node3'}
            ]
        )
        cluster_db = self.env.clusters[0]
        node1, node2, node3 = self.env.nodes
        nets_sent = [{'iface': 'eth0', 'vlans': range(100, 105)}]

        task = Task(
            name="super",
            cluster_id=cluster_db.id
        )
        task.cache = {
            "args": {
                'nodes': [{'uid': node1.id, 'networks': nets_sent},
                          {'uid': node2.id, 'networks': nets_sent},
                          {'uid': node3.id, 'networks': nets_sent}]
            }
        }
        self.db.add(task)
        self.db.commit()

        kwargs = {'task_uuid': task.uuid,
                  'status': 'ready',
                  'nodes': [{'uid': node1.id, 'networks': nets_sent},
                            {'uid': node2.id, 'networks': nets_sent}]}
        self.receiver.verify_networks_resp(**kwargs)
        self.db.flush()
        self.db.refresh(task)
        self.assertEqual(task.status, "error")
        self.assertRegexpMatches(task.message, node3.name)
        self.assertEqual(task.result, {})

    def test_verify_networks_resp_incomplete_network_data_error(self):
        # One node has single interface
        meta = self.env.default_metadata()
        mac = '02:07:43:78:4F:58'
        self.env.set_interfaces_in_meta(
            meta, [{'name': 'eth0', 'mac': mac}])

        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"api": False, 'name': 'node1'},
                {"api": False, 'name': 'node2', 'meta': meta},
                {"api": False, 'name': 'node3'}
            ]
        )
        cluster_db = self.env.clusters[0]
        node1, node2, node3 = self.env.nodes

        nets_sent = [{'iface': 'eth0', 'vlans': range(100, 105)},
                     {'iface': 'eth1', 'vlans': [106]},
                     {'iface': 'eth2', 'vlans': [107]}]

        task = Task(
            name="super",
            cluster_id=cluster_db.id
        )
        task.cache = {
            "args": {
                'nodes': [{'uid': node1.id, 'networks': nets_sent},
                          {'uid': node2.id, 'networks': nets_sent},
                          {'uid': node3.id, 'networks': nets_sent}]
            }
        }
        self.db.add(task)
        self.db.commit()

        kwargs = {'task_uuid': task.uuid,
                  'status': 'ready',
                  'nodes': [{'uid': node1.id, 'networks': nets_sent},
                            {'uid': node2.id, 'networks': []},
                            {'uid': node3.id, 'networks': nets_sent}]}
        self.receiver.verify_networks_resp(**kwargs)
        self.db.flush()
        self.db.refresh(task)
        self.assertEqual(task.status, "error")
        self.assertEqual(task.message, '')
        error_nodes = [{'uid': node2.id, 'interface': 'eth0',
                        'name': node2.name, 'mac': node2.interfaces[0].mac,
                        'absent_vlans': nets_sent[0]['vlans']},
                       {'uid': node2.id, 'interface': 'eth1',
                        'name': node2.name, 'mac': 'unknown',
                        'absent_vlans': nets_sent[1]['vlans']},
                       {'uid': node2.id, 'interface': 'eth2',
                        'name': node2.name, 'mac': 'unknown',
                        'absent_vlans': nets_sent[2]['vlans']}
                       ]

        self.assertEqual(task.result, error_nodes)

    def test_verify_networks_resp_incomplete_network_data_on_first_node(self):
        """Test verifies that when network data is incomplete on first node
        task would not fail and be erred as expected
        """
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"api": False, 'name': 'node1'},
                {"api": False, 'name': 'node2'},
            ]
        )
        cluster_db = self.env.clusters[0]
        node1, node2 = self.env.nodes
        nets_sent = [{'iface': 'eth0', 'vlans': range(100, 105)}]

        task = Task(
            name="super",
            cluster_id=cluster_db.id
        )
        task.cache = {
            "args": {
                'nodes': [{'uid': node1.id, 'networks': nets_sent},
                          {'uid': node2.id, 'networks': nets_sent}]
            }
        }

        self.db.add(task)
        self.db.commit()

        kwargs = {'task_uuid': task.uuid,
                  'status': 'ready',
                  'nodes': [{'uid': node1.id, 'networks': []},
                            {'uid': node2.id, 'networks': nets_sent}]}
        self.receiver.verify_networks_resp(**kwargs)
        self.db.flush()
        self.db.refresh(task)
        self.assertEqual(task.status, "error")
        self.assertEqual(task.message, '')
        error_nodes = [{'uid': node1.id, 'interface': 'eth0',
                        'name': node1.name, 'mac': node1.interfaces[0].mac,
                        'absent_vlans': nets_sent[0]['vlans']}]
        self.assertEqual(task.result, error_nodes)

    def test_verify_networks_resp_without_vlans_only(self):
        """Verify that network verification without vlans passes
        when there only iface without vlans configured
        """
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"api": False},
                {"api": False}
            ]
        )
        cluster_db = self.env.clusters[0]
        node1, node2 = self.env.nodes
        nets_sent = [{'iface': 'eth0', 'vlans': [0]},
                     {'iface': 'eth1', 'vlans': [0]}]

        task = Task(
            name="super",
            cluster_id=cluster_db.id
        )
        task.cache = {
            "args": {
                'nodes': [{'uid': node1.id, 'networks': nets_sent},
                          {'uid': node2.id, 'networks': nets_sent}]
            }
        }
        self.db.add(task)
        self.db.commit()

        kwargs = {'task_uuid': task.uuid,
                  'status': 'ready',
                  'nodes': [{'uid': node1.id, 'networks': nets_sent},
                            {'uid': node2.id, 'networks': nets_sent}]}
        self.receiver.verify_networks_resp(**kwargs)
        self.db.flush()
        self.db.refresh(task)
        self.assertEqual(task.status, "ready")

    def test_verify_networks_resp_without_vlans_only_erred(self):
        """Verify that network verification without vlans fails
        when not all sended info received
        """
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"api": False},
                {"api": False}
            ]
        )
        cluster_db = self.env.clusters[0]
        node1, node2 = self.env.nodes
        nets_sent = [{'iface': 'eth0', 'vlans': [0]}]
        nets_resp = [{'iface': 'eth0', 'vlans': []}]

        task = Task(
            name="super",
            cluster_id=cluster_db.id
        )
        task.cache = {
            "args": {
                'nodes': [{'uid': node1.id, 'networks': nets_sent},
                          {'uid': node2.id, 'networks': nets_sent}]
            }
        }
        self.db.add(task)
        self.db.commit()

        kwargs = {'task_uuid': task.uuid,
                  'status': 'ready',
                  'nodes': [{'uid': node1.id, 'networks': nets_resp},
                            {'uid': node2.id, 'networks': nets_resp}]}
        self.receiver.verify_networks_resp(**kwargs)
        self.db.flush()
        self.db.refresh(task)
        self.assertEqual(task.status, "error")
        error_nodes = [{'uid': node1.id, 'interface': 'eth0',
                        'name': node1.name, 'mac': node1.interfaces[0].mac,
                        'absent_vlans': nets_sent[0]['vlans']},
                       {'uid': node2.id, 'interface': 'eth0',
                        'name': node2.name, 'mac': node2.interfaces[0].mac,
                        'absent_vlans': nets_sent[0]['vlans']}]
        self.assertEqual(task.result, error_nodes)

    def test_verify_networks_resp_partially_without_vlans(self):
        """Verify that network verification partially without vlans passes
        """
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"api": False},
                {"api": False}
            ]
        )
        cluster_db = self.env.clusters[0]
        node1, node2 = self.env.nodes
        nets_sent = [{'iface': 'eth0', 'vlans': [0]},
                     {'iface': 'eth1', 'vlans': range(100, 104)}]

        task = Task(
            name="super",
            cluster_id=cluster_db.id
        )
        task.cache = {
            "args": {
                'nodes': [{'uid': node1.id, 'networks': nets_sent},
                          {'uid': node2.id, 'networks': nets_sent}]
            }
        }
        self.db.add(task)
        self.db.commit()

        kwargs = {'task_uuid': task.uuid,
                  'status': 'ready',
                  'nodes': [{'uid': node1.id, 'networks': nets_sent},
                            {'uid': node2.id, 'networks': nets_sent}]}
        self.receiver.verify_networks_resp(**kwargs)
        self.db.flush()
        self.db.refresh(task)
        self.assertEqual(task.status, "ready")


class TestDhcpCheckTask(BaseIntegrationTest):

    def setUp(self):
        super(TestDhcpCheckTask, self).setUp()
        self.receiver = rcvr.NailgunReceiver()
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"api": False},
                {"api": False}
            ]
        )
        cluster_db = self.env.clusters[0]
        self.node1, self.node2 = self.env.nodes

        self.task = Task(
            name="check_dhcp",
            cluster_id=cluster_db.id
        )
        self.db.add(self.task)
        self.db.commit()

    def test_check_dhcp_resp_master_mac(self):
        kwargs = {
            'task_uuid': self.task.uuid,
            'status': 'ready',
            'nodes': [{'uid': self.node1.id,
                      'status': 'ready',
                      'data': [{'mac': settings.ADMIN_NETWORK['mac'],
                               'server_id': '10.20.0.157',
                               'yiaddr': '10.20.0.133',
                               'iface': 'eth0'}]},
                      {'uid': self.node2.id,
                       'status': 'ready',
                       'data': [{'mac': settings.ADMIN_NETWORK['mac'],
                                'server_id': '10.20.0.20',
                                'yiaddr': '10.20.0.131',
                                'iface': 'eth0'}]}]
        }

        self.receiver.check_dhcp_resp(**kwargs)
        self.db.flush()
        self.db.refresh(self.task)
        self.assertEqual(self.task.status, "ready")
        self.assertEqual(self.task.result, {})

    def test_check_dhcp_resp_roque_dhcp_mac(self):
        kwargs = {
            'task_uuid': self.task.uuid,
            'status': 'ready',
            'nodes': [{'uid': str(self.node1.id),
                      'status': 'ready',
                      'data': [{'mac': 'ee:ae:c5:e0:f5:17',
                               'server_id': '10.20.0.157',
                               'yiaddr': '10.20.0.133',
                               'iface': 'eth0'}]},
                      {'uid': str(self.node2.id),
                       'status': 'ready',
                       'data': [{'mac': settings.ADMIN_NETWORK['mac'],
                                'server_id': '10.20.0.20',
                                'yiaddr': '10.20.0.131',
                                'iface': 'eth0'}]}]
        }
        self.receiver.check_dhcp_resp(**kwargs)
        self.db.flush()
        self.db.refresh(self.task)
        self.assertEqual(self.task.status, "error")

    def test_check_dhcp_resp_empty_nodes(self):
        kwargs = {
            'task_uuid': self.task.uuid,
            'status': 'ready'
        }
        self.receiver.check_dhcp_resp(**kwargs)
        self.db.flush()
        self.db.refresh(self.task)
        self.assertEqual(self.task.status, "ready")
        self.assertEqual(self.task.result, {})

    def test_check_dhcp_resp_empty_nodes_erred(self):
        kwargs = {
            'task_uuid': self.task.uuid,
            'status': 'error'
        }
        self.receiver.check_dhcp_resp(**kwargs)
        self.db.flush()
        self.db.refresh(self.task)
        self.assertEqual(self.task.status, 'error')
        self.assertEqual(self.task.result, {})


class TestClusterUpdate(BaseIntegrationTest):

    def setUp(self):
        super(TestClusterUpdate, self).setUp()
        self.receiver = rcvr.NailgunReceiver()
        cluster_id = self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"api": False, "status": consts.NODE_STATUSES.deploying},
                {"api": False, "status": consts.NODE_STATUSES.deploying}],
        )['id']
        self.cluster = self.db.query(Cluster).get(cluster_id)
        self.cluster.pending_release_id = self.cluster.release_id
        self.cluster.status = consts.CLUSTER_STATUSES.update
        self.db.commit()

        self.task = Task(
            uuid=str(uuid.uuid4()),
            name=consts.TASK_NAMES.update,
            cluster_id=self.cluster.id
        )
        self.db.add(self.task)
        self.db.commit()

    def test_node_deploy_resp_ready(self):
        node1, node2 = self.env.nodes
        kwargs = {'task_uuid': self.task.uuid,
                  'status': consts.TASK_STATUSES.ready,
                  'nodes': [
                      {'uid': node1.id, 'status': consts.NODE_STATUSES.ready},
                      {'uid': node2.id, 'status': consts.NODE_STATUSES.ready}]}
        self.receiver.deploy_resp(**kwargs)

        self.assertEqual(
            (node1.status, node2.status),
            (consts.NODE_STATUSES.ready, consts.NODE_STATUSES.ready))
        self.assertEqual(self.task.status, consts.TASK_STATUSES.ready)
        self.assertEqual(self.cluster.status,
                         consts.CLUSTER_STATUSES.operational)
        self.assertEqual(self.cluster.pending_release_id, None)

    def test_node_deploy_resp_node_error(self):
        node1, node2 = self.env.nodes
        kwargs = {'task_uuid': self.task.uuid,
                  'nodes': [
                      {'uid': node1.id, 'status': consts.NODE_STATUSES.ready},
                      {'uid': node2.id, 'status': consts.NODE_STATUSES.error}]}
        self.receiver.deploy_resp(**kwargs)

        self.assertEqual(
            (node1.status, node2.status),
            (consts.NODE_STATUSES.ready, consts.NODE_STATUSES.error))
        self.assertEqual(self.task.status, consts.TASK_STATUSES.running)
        self.assertEqual(self.cluster.status, consts.CLUSTER_STATUSES.update)
        self.assertEqual(self.cluster.pending_release_id,
                         self.cluster.release_id)

    def test_node_deploy_resp_update_error(self):
        node1, node2 = self.env.nodes
        kwargs = {'task_uuid': self.task.uuid,
                  'status': consts.TASK_STATUSES.error,
                  'nodes': [
                      {'uid': node1.id, 'status': consts.NODE_STATUSES.ready},
                      {'uid': node2.id, 'status': consts.NODE_STATUSES.error}]}
        self.receiver.deploy_resp(**kwargs)

        self.assertEqual(
            (node1.status, node2.status),
            (consts.NODE_STATUSES.ready, consts.NODE_STATUSES.error))
        self.assertEqual(self.task.status, consts.TASK_STATUSES.error)
        self.assertEqual(self.cluster.status,
                         consts.CLUSTER_STATUSES.update_error)
        self.assertEqual(self.cluster.pending_release_id,
                         self.cluster.release_id)

    def test_node_deploy_resp_update_error_wo_explicit_nodes(self):
        node1, node2 = self.env.nodes
        kwargs = {'task_uuid': self.task.uuid,
                  'status': consts.TASK_STATUSES.error}
        self.receiver.deploy_resp(**kwargs)

        self.assertEqual(
            (node1.status, node2.status),
            (consts.NODE_STATUSES.error, consts.NODE_STATUSES.error))
        self.assertEqual(self.task.status, consts.TASK_STATUSES.error)
        self.assertEqual(self.cluster.status,
                         consts.CLUSTER_STATUSES.update_error)
        self.assertEqual(self.cluster.pending_release_id,
                         self.cluster.release_id)


class TestConsumer(BaseIntegrationTest):

    def setUp(self):
        super(TestConsumer, self).setUp()
        self.receiver = rcvr.NailgunReceiver()

    def test_node_deploy_resp(self):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"api": False},
                {"api": False}]
        )

        node, node2 = self.env.nodes

        task = Task(
            uuid=str(uuid.uuid4()),
            name="deploy",
            cluster_id=self.env.clusters[0].id
        )
        self.db.add(task)
        self.db.commit()

        kwargs = {'task_uuid': task.uuid,
                  'nodes': [{'uid': node.id, 'status': 'deploying'},
                            {'uid': node2.id, 'status': 'error'}]}
        self.receiver.deploy_resp(**kwargs)
        self.db.refresh(node)
        self.db.refresh(node2)
        self.db.refresh(task)
        self.assertEqual((node.status, node2.status), ("deploying", "error"))
        # it is running because we don't stop deployment
        # if there are error nodes
        self.assertEqual(task.status, "running")

    def test_node_provision_resp(self):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"api": False},
                {"api": False}])
        node = self.env.nodes[0]
        node2 = self.env.nodes[1]

        task = Task(
            name='provision',
            cluster_id=self.env.clusters[0].id)

        self.db.add(task)
        self.db.commit()

        kwargs = {'task_uuid': task.uuid,
                  'status': 'running',
                  'nodes': [
                      {'uid': node.id,
                       'status': 'provisioning',
                       'progress': 50},
                      {'uid': node2.id,
                       'status': 'provisioning',
                       'progress': 50}]}

        self.receiver.provision_resp(**kwargs)
        self.db.refresh(task)

        self.assertEqual(task.progress, 50)

    def test_action_log_updating(self):

        def check_write_logs_from_receiver(**kwargs):
            task = objects.Task.create({'name': kwargs['task_name'],
                                        'cluster_id': kwargs['cluster_id']})

            action_log_kwargs = {
                'action_group': 'test_cluster_changes',
                'action_name': 'test_provision_action',
                'action_type': consts.ACTION_TYPES.nailgun_task,
                'additional_info': {},
                'is_sent': False,
                'cluster_id': task.cluster.id,
                'task_uuid': task.uuid,
                'start_timestamp': datetime.datetime.now()
            }
            al = objects.ActionLog.create(action_log_kwargs)

            rpc_resp_kwargs = {
                'task_uuid': task.uuid,
                'status': kwargs['task_status'],
                'nodes': [
                    {
                        'uid': node_id,
                        'status': kwargs['status_for_nodes'],
                        'progress': 100
                    }
                    for node_id in kwargs['node_ids']
                ]
            }
            kwargs['rpc_resp'](**rpc_resp_kwargs)
            self.db.flush()

            self.db.refresh(al)

            # check that action_log entry was updated
            # in receiver's methods' code
            self.assertIsNotNone(al.end_timestamp)
            self.assertIn('nodes_from_resp',
                          al.additional_info)
            self.assertEqual(set(al.additional_info['nodes_from_resp']),
                             set(kwargs['node_ids']))
            self.assertEqual(kwargs['task_status'],
                             al.additional_info.get('ended_with_status'))

            # clean data
            self.db.delete(task)
            self.db.delete(al)
            self.db.commit()

        self.env.create(
            nodes_kwargs=[
                {'api': False},
                {'api': False}
            ]
        )

        node, node2 = self.env.nodes

        test_cases_kwargs = [
            {'task_name': consts.TASK_NAMES.provision,
             'task_status': consts.TASK_STATUSES.ready,
             'status_for_nodes': consts.NODE_STATUSES.provisioned,
             'rpc_resp': self.receiver.provision_resp},
            {'task_name': 'deployment',
             'task_status': consts.TASK_STATUSES.error,
             'status_for_nodes': consts.NODE_STATUSES.error,
             'rpc_resp': self.receiver.deploy_resp}
        ]

        for kw in test_cases_kwargs:
            kw['cluster_id'] = self.env.clusters[0].id
            kw['node_ids'] = [node.id, node2.id]

            check_write_logs_from_receiver(**kw)

    def test_task_progress(self):
        self.env.create_cluster()

        task = Task(
            uuid=str(uuid.uuid4()),
            name="super",
            status="running",
            cluster_id=self.env.clusters[0].id
        )
        self.db.add(task)
        self.db.commit()
        kwargs = {'task_uuid': task.uuid, 'progress': 20}
        self.receiver.deploy_resp(**kwargs)
        self.db.refresh(task)
        self.assertEqual(task.progress, 20)
        self.assertEqual(task.status, "running")

    def test_node_deletion_subtask_progress(self):
        supertask = Task(
            uuid=str(uuid.uuid4()),
            name="super",
            status="running"
        )

        self.db.add(supertask)
        task_deletion = supertask.create_subtask("node_deletion")
        task_provision = supertask.create_subtask("provision", weight=0.4)
        self.db.commit()

        subtask_progress = random.randint(1, 20)

        deletion_kwargs = {'task_uuid': task_deletion.uuid,
                           'progress': subtask_progress,
                           'status': 'running'}
        provision_kwargs = {'task_uuid': task_provision.uuid,
                            'progress': subtask_progress,
                            'status': 'running'}

        def progress_difference():
            self.receiver.provision_resp(**provision_kwargs)
            self.db.commit()

            self.db.refresh(task_provision)
            self.assertEqual(task_provision.progress, subtask_progress)

            self.db.refresh(supertask)
            progress_before_delete_subtask = supertask.progress

            self.receiver.remove_nodes_resp(**deletion_kwargs)
            self.db.commit()

            self.db.refresh(task_deletion)
            self.assertEqual(task_deletion.progress, subtask_progress)

            self.db.refresh(supertask)
            progress_after_delete_subtask = supertask.progress

            return abs(progress_after_delete_subtask -
                       progress_before_delete_subtask)

        without_coeff = progress_difference()

        task_deletion.progress = 0
        task_deletion.weight = 0.5
        self.db.merge(task_deletion)

        task_provision.progress = 0
        self.db.merge(task_provision)

        supertask.progress = 0
        self.db.merge(supertask)

        self.db.commit()

        with_coeff = progress_difference()

        # some freaking magic is here but haven't found
        # better way to test what is already working
        self.assertTrue((without_coeff / with_coeff) < 2)

    def test_proper_progress_calculation(self):
        supertask = Task(
            uuid=str(uuid.uuid4()),
            name="super",
            status="running"
        )

        self.db.add(supertask)
        self.db.commit()

        subtask_weight = 0.4
        task_deletion = supertask.create_subtask("node_deletion",
                                                 weight=subtask_weight)
        task_provision = supertask.create_subtask("provision",
                                                  weight=subtask_weight)

        subtask_progress = random.randint(1, 20)

        deletion_kwargs = {'task_uuid': task_deletion.uuid,
                           'progress': subtask_progress,
                           'status': 'running'}
        provision_kwargs = {'task_uuid': task_provision.uuid,
                            'progress': subtask_progress,
                            'status': 'running'}

        self.receiver.provision_resp(**provision_kwargs)
        self.db.commit()
        self.receiver.remove_nodes_resp(**deletion_kwargs)
        self.db.commit()

        self.db.refresh(task_deletion)
        self.db.refresh(task_provision)
        self.db.refresh(supertask)

        calculated_progress = helpers.\
            TaskHelper.calculate_parent_task_progress(
                [task_deletion, task_provision]
            )

        self.assertEqual(supertask.progress, calculated_progress)

    def test_error_node_progress(self):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"api": False}
            ]
        )
        task = Task(
            uuid=str(uuid.uuid4()),
            name="super",
            status="running",
            cluster_id=self.env.clusters[0].id
        )
        self.db.add(task)
        self.db.commit()
        kwargs = {
            'task_uuid': task.uuid,
            'progress': 20,
            'nodes': [
                {
                    'uid': self.env.nodes[0].id,
                    'status': 'error',
                    'progress': 50
                }
            ]
        }
        self.receiver.deploy_resp(**kwargs)
        self.db.refresh(self.env.nodes[0])
        self.assertEqual(self.env.nodes[0].progress, 100)

    def test_remove_nodes_resp(self):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"api": False},
                {"api": False}
            ]
        )
        cluster_db = self.env.clusters[0]
        node1, node2 = self.env.nodes

        task = Task(
            uuid=str(uuid.uuid4()),
            name="super",
            cluster_id=cluster_db.id
        )
        self.db.add(task)
        self.db.commit()

        kwargs = {'task_uuid': task.uuid,
                  'progress': 100,
                  'status': 'ready',
                  'nodes': [{'uid': node1.id},
                            {'uid': str(node2.id)}]}

        self.receiver.remove_nodes_resp(**kwargs)
        self.db.refresh(task)
        self.assertEqual(task.status, "ready")
        nodes_db = self.db.query(Node).all()
        self.assertEqual(len(nodes_db), 0)

    def test_remove_nodes_resp_failure(self):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"api": False},
                {"api": False}
            ]
        )
        cluster_db = self.env.clusters[0]
        node1, node2 = self.env.nodes

        task = Task(
            uuid=str(uuid.uuid4()),
            name="super",
            cluster_id=cluster_db.id
        )
        self.db.add(task)
        self.db.commit()

        kwargs = {'task_uuid': task.uuid,
                  'progress': 100,
                  'status': 'error',
                  'nodes': [],
                  'error_nodes': [{'uid': node1.id,
                                   'error': "RPC method failed"}]}

        self.receiver.remove_nodes_resp(**kwargs)
        self.db.refresh(task)
        self.assertEqual(task.status, "error")
        nodes_db = self.db.query(Node).all()
        error_node = self.db.query(Node).get(node1.id)
        self.db.refresh(error_node)
        self.assertEqual(len(nodes_db), 2)
        self.assertEqual(error_node.status, "error")

    def test_remove_cluster_resp(self):
        cluster = self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"api": False},
                {"api": False}
            ]
        )
        cluster_db = self.db.query(Cluster).get(cluster["id"])
        cluster_id = cluster_db.id
        node1, node2 = self.env.nodes
        node1_id, node2_id = [n.id for n in self.env.nodes]
        self.env.create_notification(
            cluster_id=cluster_id
        )
        group_id = objects.Cluster.get_default_group(cluster_db).id

        task = Task(
            uuid=str(uuid.uuid4()),
            name="cluster_deletion",
            cluster_id=cluster_id
        )
        self.db.add(task)
        self.db.commit()

        kwargs = {'task_uuid': task.uuid,
                  'progress': 100,
                  'status': 'ready',
                  'nodes': [{'uid': node1.id},
                            {'uid': str(node2.id)}],
                  'error_nodes': []
                  }

        self.receiver.remove_cluster_resp(**kwargs)
        self.db.commit()

        nodes_db = self.db.query(Node)\
            .filter_by(cluster_id=cluster_id).all()
        self.assertEqual(len(nodes_db), 0)

        ip_db = self.db.query(IPAddr)\
            .filter(IPAddr.node.in_([node1_id, node2_id])).all()
        self.assertEqual(len(ip_db), 0)

        attrs_db = self.db.query(Attributes)\
            .filter_by(cluster_id=cluster_id).all()
        self.assertEqual(len(attrs_db), 0)

        nots_db = self.db.query(Notification)\
            .filter_by(cluster_id=cluster_id).all()
        self.assertEqual(len(nots_db), 0)

        nets_db = self.db.query(NetworkGroup).\
            filter(NetworkGroup.group_id ==
                   group_id).all()
        self.assertEquals(len(nets_db), 0)

        task_db = self.db.query(Task)\
            .filter_by(cluster_id=cluster_id).all()
        self.assertEqual(len(task_db), 0)

        cluster_db = self.db.query(Cluster).get(cluster_id)
        self.assertIsNone(cluster_db)

    def test_remove_cluster_resp_failed(self):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"api": False},
                {"api": False}
            ]
        )
        cluster_db = self.env.clusters[0]
        node1, node2 = self.env.nodes
        self.env.create_notification(
            cluster_id=cluster_db.id
        )

        task = Task(
            uuid=str(uuid.uuid4()),
            name="cluster_deletion",
            cluster_id=cluster_db.id
        )
        self.db.add(task)
        self.db.commit()

        kwargs = {'task_uuid': task.uuid,
                  'progress': 100,
                  'status': 'error',
                  'nodes': [{'uid': node1.id}],
                  'error_nodes': [{'uid': node1.id,
                                   'error': "RPC method failed"}],
                  }

        self.receiver.remove_cluster_resp(**kwargs)
        self.db.refresh(task)
        self.assertEqual(task.status, "error")

        nodes_db = self.db.query(Node)\
            .filter_by(cluster_id=cluster_db.id).all()
        self.assertNotEqual(len(nodes_db), 0)

        attrs_db = self.db.query(Attributes)\
            .filter_by(cluster_id=cluster_db.id).all()
        self.assertNotEqual(len(attrs_db), 0)

        nots_db = self.db.query(Notification)\
            .filter_by(cluster_id=cluster_db.id).all()
        self.assertNotEqual(len(nots_db), 0)

        nets_db = self.db.query(NetworkGroup).\
            filter(NetworkGroup.group_id ==
                   objects.Cluster.get_default_group(
                       self.env.clusters[0]).id).\
            all()
        self.assertNotEqual(len(nets_db), 0)
