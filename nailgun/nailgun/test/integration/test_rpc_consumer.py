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
import mock
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
from nailgun.utils import reverse

from nailgun import consts

from nailgun import objects


class BaseReciverTestCase(BaseIntegrationTest):

    def setUp(self):
        super(BaseReciverTestCase, self).setUp()
        self.receiver = rcvr.NailgunReceiver()


class TestVerifyNetworks(BaseReciverTestCase):

    def nodes_message(self, nodes, networks):
        nodes_message = []
        for n in nodes:
            nodes_message.append(
                {'uid': n.id,
                 'name': n.name,
                 'status': n.status,
                 'networks': networks})
        return nodes_message

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
                "nodes": self.nodes_message((node1, node2), nets),
                "offline": 0,
            }
        }
        self.db.add(task)
        self.db.commit()

        kwargs = {'task_uuid': task.uuid,
                  'status': 'ready',
                  'nodes': self.nodes_message((node1, node2), nets)}

        self.receiver.verify_networks_resp(**kwargs)
        self.db.flush()
        self.db.refresh(task)
        self.assertEqual(task.status, "ready")
        self.assertEqual(task.message, '')

    def test_verify_networks_error_and_notice_are_concatenated(self):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"api": False},
                {"api": False},
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
                "nodes": self.nodes_message((node1, node2), nets),
                "offline": 2,
            }
        }
        self.db.add(task)
        self.db.flush()

        custom_error = 'CustomError'
        kwargs = {'task_uuid': task.uuid,
                  'status': 'error',
                  'nodes': self.nodes_message((node1, node2), nets),
                  'error': custom_error}

        self.receiver.verify_networks_resp(**kwargs)
        self.db.flush()
        self.db.refresh(task)
        self.assertEqual(task.status, "error")
        offline_notice = 'Notice: 2 node(s) were offline during connectivity' \
                         ' check so they were skipped from the check.'
        self.assertEqual(task.message,
                         '\n'.join((custom_error, offline_notice)))

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
                'nodes': self.nodes_message((node1, node2), nets_sent),
                'offline': 0,
            }
        }
        self.db.add(task)
        self.db.commit()

        kwargs = {'task_uuid': task.uuid,
                  'status': 'ready',
                  'nodes': self.nodes_message((node1, node2), nets_resp)}
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
                'nodes': self.nodes_message((node1, node2), nets_sent),
                'offline': 0,
            }
        }
        self.db.add(task)
        self.db.commit()

        kwargs = {'task_uuid': task.uuid,
                  'status': 'ready',
                  'nodes': self.nodes_message((node1, node2), nets_resp)}
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
        error_nodes = [{'uid': node1.id,
                        'interface': 'eth0',
                        'name': node1.name,
                        'absent_vlans': [104],
                        'mac': node1.interfaces[0].mac},
                       {'uid': node2.id,
                        'interface': 'eth0',
                        'name': node2.name,
                        'absent_vlans': [104],
                        'mac': 'unknown'}]
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
                'nodes': self.nodes_message((node1, node2), nets_sent),
                'offline': 0,
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
                'nodes': self.nodes_message((node1, node2), nets_sent),
                'offline': 0,
            }
        }
        self.db.add(task)
        self.db.commit()

        kwargs = {'task_uuid': task.uuid,
                  'status': 'ready',
                  'nodes': self.nodes_message((node1, node2, node3),
                                              nets_sent)}
        self.receiver.verify_networks_resp(**kwargs)
        self.db.flush()
        self.db.refresh(task)
        self.assertEqual(task.status, "ready")
        self.assertEqual(task.message, '')

    def test_verify_networks_with_dhcp_subtask(self):
        """verify_networks status depends on dhcp subtask

        Test verifies that when dhcp subtask is ready and
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
                'nodes': self.nodes_message((node1, node2), nets_sent),
                'offline': 0,
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
                  'nodes': self.nodes_message((node1, node2), [])}
        kwargs['nodes'][0]['networks'] = nets_sent
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
                'nodes': self.nodes_message((node1, node2), nets_sent),
                'offline': 0,
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
                  'nodes': self.nodes_message((node1, node2), [])}
        kwargs['nodes'][0]['networks'] = nets_sent
        self.receiver.verify_networks_resp(**kwargs)

        self.assertEqual(task.status, "error")
        self.assertEqual(task.message, u'DHCP ERROR')

        task.result[0]['absent_vlans'] = sorted(task.result[0]['absent_vlans'])
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
                'nodes': self.nodes_message((node1, node2, node3), nets_sent),
                'offline': 0,
            }
        }
        self.db.add(task)
        self.db.commit()

        kwargs = {'task_uuid': task.uuid,
                  'status': 'ready',
                  'nodes': self.nodes_message((node1, node2),
                                              nets_sent)}
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
                'nodes': self.nodes_message((node1, node2, node3), nets_sent),
                'offline': 0,
            }
        }
        self.db.add(task)
        self.db.commit()

        kwargs = {'task_uuid': task.uuid,
                  'status': 'ready',
                  'nodes': self.nodes_message((node1, node2, node3),
                                              nets_sent)}
        kwargs['nodes'][1]['networks'] = []
        self.receiver.verify_networks_resp(**kwargs)
        self.db.flush()
        self.db.refresh(task)
        self.assertEqual(task.status, "error")
        self.assertEqual(task.message, '')
        error_nodes = [{'uid': node2.id,
                        'interface': 'eth0',
                        'name': node2.name,
                        'mac': node2.interfaces[0].mac,
                        'absent_vlans': nets_sent[0]['vlans']},
                       {'uid': node2.id,
                        'interface': 'eth1',
                        'name': node2.name,
                        'mac': 'unknown',
                        'absent_vlans': nets_sent[1]['vlans']},
                       {'uid': node2.id,
                        'interface': 'eth2',
                        'name': node2.name,
                        'mac': 'unknown',
                        'absent_vlans': nets_sent[2]['vlans']}
                       ]

        self.assertItemsEqual(task.result, error_nodes)

    def test_verify_networks_resp_incomplete_network_data_on_first_node(self):
        """First node network data incompletion causes task fail"""
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
                'nodes': self.nodes_message((node1, node2), nets_sent),
                'offline': 0,
            }
        }

        self.db.add(task)
        self.db.commit()

        kwargs = {'task_uuid': task.uuid,
                  'status': 'ready',
                  'nodes': self.nodes_message((node1, node2), [])}
        kwargs['nodes'][1]['networks'] = nets_sent
        self.receiver.verify_networks_resp(**kwargs)
        self.db.flush()
        self.db.refresh(task)
        self.assertEqual(task.status, "error")
        self.assertEqual(task.message, '')
        error_nodes = [{'uid': node1.id,
                        'interface': 'eth0',
                        'name': node1.name,
                        'mac': node1.interfaces[0].mac,
                        'absent_vlans': sorted(nets_sent[0]['vlans'])}]
        task.result[0]['absent_vlans'] = sorted(task.result[0]['absent_vlans'])

        self.assertEqual(task.result, error_nodes)

    def test_verify_networks_resp_without_vlans_only(self):
        """Net verification without vlans

        Passes when only iface without vlans configured
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
                'nodes': self.nodes_message((node1, node2), nets_sent),
                'offline': 0,
            }
        }
        self.db.add(task)
        self.db.commit()

        kwargs = {'task_uuid': task.uuid,
                  'status': 'ready',
                  'nodes': self.nodes_message((node1, node2), nets_sent)}
        self.receiver.verify_networks_resp(**kwargs)
        self.db.flush()
        self.db.refresh(task)
        self.assertEqual(task.status, "ready")

    def test_verify_networks_resp_without_vlans_only_erred(self):
        """Net verification without vlans fails when not all info received"""
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
                'nodes': self.nodes_message((node1, node2), nets_sent),
                'offline': 0,
            }
        }
        self.db.add(task)
        self.db.commit()

        kwargs = {'task_uuid': task.uuid,
                  'status': 'ready',
                  'nodes': self.nodes_message((node1, node2), nets_resp)}
        self.receiver.verify_networks_resp(**kwargs)
        self.db.flush()
        self.db.refresh(task)
        self.assertEqual(task.status, "error")
        error_nodes = [{'uid': node1.id,
                        'interface': 'eth0',
                        'name': node1.name,
                        'mac': node1.interfaces[0].mac,
                        'absent_vlans': nets_sent[0]['vlans']},
                       {'uid': node2.id,
                        'interface': 'eth0',
                        'name': node2.name,
                        'mac': node2.interfaces[0].mac,
                        'absent_vlans': nets_sent[0]['vlans']}]
        self.assertEqual(task.result, error_nodes)

    def test_verify_networks_resp_partially_without_vlans(self):
        """Verify that network verification partially without vlans passes"""
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
                'nodes': self.nodes_message((node1, node2), nets_sent),
                'offline': 0,
            }
        }
        self.db.add(task)
        self.db.commit()

        kwargs = {'task_uuid': task.uuid,
                  'status': 'ready',
                  'nodes': self.nodes_message((node1, node2), nets_sent)}
        self.receiver.verify_networks_resp(**kwargs)
        self.db.flush()
        self.db.refresh(task)
        self.assertEqual(task.status, "ready")

    def test_verify_networks_with_excluded_networks(self):
        """Verify that network verification can exclude interfaces"""
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
        nets_excluded = [{'iface': 'eth3'}, {'iface': 'eth4'}]

        task = Task(
            name="super",
            cluster_id=cluster_db.id
        )
        task.cache = {
            "args": {
                'nodes': [
                    {
                        'uid': node1.id,
                        'name': node1.name,
                        'status': node1.status,
                        'networks': nets_sent,
                        'excluded_networks': nets_excluded
                    },
                    {
                        'uid': node2.id,
                        'name': node2.name,
                        'status': node2.status,
                        'networks': nets_sent,
                        'excluded_networks': nets_excluded
                    }
                ],
                'offline': 0,
            }
        }
        self.db.add(task)
        self.db.commit()

        kwargs = {
            'task_uuid': task.uuid,
            'status': 'ready',
            'nodes': [
                {
                    'uid': node1.id,
                    'name': node1.name,
                    'status': node1.status,
                    'networks': nets_sent,
                    'excluded_networks': nets_excluded
                },
                {
                    'uid': node2.id,
                    'name': node2.name,
                    'status': node2.status,
                    'networks': nets_sent,
                    'excluded_networks': nets_excluded
                }
            ]
        }
        self.receiver.verify_networks_resp(**kwargs)
        self.db.flush()
        self.db.refresh(task)
        self.assertEqual(task.status, "ready")
        expected_message = 'Notice: some interfaces were skipped from' \
                           ' connectivity checking because this version' \
                           ' of Fuel cannot establish LACP on Bootstrap' \
                           ' nodes. Only interfaces of successfully' \
                           ' deployed nodes may be checked with LACP' \
                           ' enabled. The list of skipped interfaces:' \
                           ' node {0} [eth3, eth4], node {1} [eth3, eth4].' \
                           .format(node1.name, node2.name)

        self.assertEqual(task.message, expected_message)


class TestDhcpCheckTask(BaseReciverTestCase):

    def setUp(self):
        super(TestDhcpCheckTask, self).setUp()
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


class TestClusterUpdate(BaseReciverTestCase):

    def setUp(self):
        super(TestClusterUpdate, self).setUp()
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


class TestConsumer(BaseReciverTestCase):

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
                'action_name': kwargs["task_name"],
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

    def _prepare_task(self, name):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"api": False},
                {"api": False}
            ]
        )
        task = Task(
            uuid=str(uuid.uuid4()),
            name=name,
            status=consts.TASK_STATUSES.running,
            cluster_id=self.env.clusters[0].id
        )
        self.db.add(task)
        self.db.flush()
        return task

    def _prepare_sub_task(self, name):
        task = self._prepare_task(consts.TASK_NAMES.super)
        sub_task = Task(
            uuid=str(uuid.uuid4()),
            name=name,
            status=consts.TASK_STATUSES.running,
            cluster_id=self.env.clusters[0].id,
            parent_id=task.id
        )
        self.db.add(sub_task)
        self.db.flush()
        return sub_task

    def _create_resp_kwargs(
            self,
            task_uuid,
            status,
            progress,
            node_status,
            node_progress
    ):
        return {
            'task_uuid': task_uuid,
            'progress': progress,
            'status': status,
            'nodes': [
                {
                    'uid': self.env.nodes[0].id,
                    'status': node_status,
                    'progress': node_progress
                }
            ]
        }

    def test_deploy_resp_error_node_progress(self):
        task = self._prepare_task(consts.TASK_NAMES.deployment)
        kwargs = self._create_resp_kwargs(
            task.uuid, consts.TASK_STATUSES.running, 20,
            consts.TASK_STATUSES.error, 50
        )
        self.receiver.deploy_resp(**kwargs)
        self.db.refresh(self.env.nodes[0])
        self.assertEqual(self.env.nodes[0].progress, 100)

    def test_provision_resp_error_node_progress(self):
        task = self._prepare_task(consts.TASK_NAMES.provision)
        kwargs = self._create_resp_kwargs(
            task.uuid, consts.TASK_STATUSES.running, 20,
            consts.TASK_STATUSES.error, 50
        )
        self.receiver.provision_resp(**kwargs)
        self.db.refresh(self.env.nodes[0])
        self.assertEqual(self.env.nodes[0].progress, 100)

    def test_provision_resp_error_notification(self):
        task = self._prepare_task(consts.TASK_NAMES.provision)
        kwargs = self._create_resp_kwargs(
            task.uuid, consts.TASK_STATUSES.error, 20,
            consts.TASK_STATUSES.error, 50
        )
        self.receiver.provision_resp(**kwargs)
        notifications_number = self.db.query(Notification).filter_by(
            cluster_id=task.cluster_id
        ).count()
        self.assertEqual(1, notifications_number)

    def test_provision_resp_sub_task_no_error_notification(self):
        sub_task = self._prepare_sub_task(consts.TASK_NAMES.provision)
        kwargs = self._create_resp_kwargs(
            sub_task.uuid, consts.TASK_STATUSES.error, 20,
            consts.TASK_STATUSES.error, 50
        )
        self.receiver.provision_resp(**kwargs)
        notifications_number = self.db.query(Notification).filter_by(
            cluster_id=sub_task.cluster_id
        ).count()
        self.assertEqual(0, notifications_number)

    def test_provision_resp_success_notification(self):
        task = self._prepare_task(consts.TASK_NAMES.provision)
        kwargs = self._create_resp_kwargs(
            task.uuid, consts.TASK_STATUSES.ready, 100,
            consts.TASK_STATUSES.ready, 100
        )

        self.receiver.provision_resp(**kwargs)
        notifications_number = self.db.query(Notification).filter_by(
            cluster_id=task.cluster_id
        ).count()
        self.assertEqual(1, notifications_number)

    def test_provision_resp_sub_task_no_success_notification(self):
        sub_task = self._prepare_sub_task(consts.TASK_NAMES.provision)
        kwargs = self._create_resp_kwargs(
            sub_task.uuid, consts.TASK_STATUSES.ready, 100,
            consts.TASK_STATUSES.ready, 100
        )
        self.receiver.provision_resp(**kwargs)
        notifications_number = self.db.query(Notification).filter_by(
            cluster_id=sub_task.cluster_id
        ).count()
        self.assertEqual(0, notifications_number)

    def test_provision_resp_nodes_failed(self):
        task = self._prepare_task(consts.TASK_NAMES.provision)
        kwargs = {
            'task_uuid': task.uuid,
            'progress': 20,
            'status': consts.TASK_STATUSES.ready,
            'nodes': [
                {
                    'uid': self.env.nodes[0].id,
                    'status': consts.TASK_STATUSES.error,
                    'progress': 50
                },
                {
                    'uid': self.env.nodes[1].id,
                    'status': consts.TASK_STATUSES.error,
                    'progress': 50
                }
            ]
        }
        self.receiver.provision_resp(**kwargs)
        notifications_number = self.db.query(Notification).filter_by(
            cluster_id=task.cluster_id).count()
        self.assertEqual(1, notifications_number)
        self.assertRegexpMatches(
            task.message,
            u"Provision has failed\. Check these nodes:\n'(.*)', '(.*)'")

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
        with mock.patch(
            'nailgun.rpc.receiver.logs_utils.delete_node_logs') \
                as mdelete_node_logs:
            self.receiver.remove_nodes_resp(**kwargs)

        self.assertEqual(len(self.env.nodes), mdelete_node_logs.call_count)

        test_nodes = [arg[0][0] for arg in mdelete_node_logs.call_args_list]
        self.assertItemsEqual(self.env.nodes, test_nodes)

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

    def test_remove_images_resp(self):
        self.env.create()
        cluster_db = self.env.clusters[0]

        task = Task(
            name=consts.TASK_NAMES.remove_images,
            cluster_id=cluster_db.id
        )
        self.db.add(task)
        self.db.flush()

        kwargs = {
            'task_uuid': task.uuid,
            'progress': 100,
            'status': consts.TASK_STATUSES.ready,
        }

        self.receiver.remove_images_resp(**kwargs)

        self.db().refresh(task)
        self.assertEqual(consts.TASK_STATUSES.ready, task.status)

    def test_remove_images_resp_failed(self):
        self.env.create()
        cluster_db = self.env.clusters[0]

        task = Task(
            name=consts.TASK_NAMES.remove_images,
            cluster_id=cluster_db.id
        )
        self.db.add(task)
        self.db.flush()

        kwargs = {
            'task_uuid': task.uuid,
            'progress': 100,
            'status': consts.TASK_STATUSES.error,
        }

        self.receiver.remove_images_resp(**kwargs)

        self.db().refresh(task)
        self.assertEqual(consts.TASK_STATUSES.error, task.status)

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

    def test_provision_resp_master_uid(self):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"api": False, "status": consts.NODE_STATUSES.provisioning},
                {"api": False, "status": consts.NODE_STATUSES.provisioning},
            ]
        )
        cluster = self.env.clusters[0]
        node1, node2 = self.env.nodes

        task = Task(
            uuid=str(uuid.uuid4()),
            name=consts.TASK_NAMES.provision,
            cluster_id=cluster.id)
        self.db.add(task)
        self.db.flush()

        self.receiver.provision_resp(**{
            'task_uuid': task.uuid,
            'nodes': [
                {
                    'uid': 'master',
                    'status': 'error',
                    'error_type': 'execute_tasks',
                    'role': 'hook',
                    'hook': None
                }
            ]})

        self.assertEqual(cluster.status, consts.CLUSTER_STATUSES.error)

        self.assertEqual(node1.status, consts.NODE_STATUSES.error)
        self.assertEqual(node1.error_type, consts.NODE_ERRORS.provision)

        self.assertEqual(node2.status, consts.NODE_STATUSES.error)
        self.assertEqual(node2.error_type, consts.NODE_ERRORS.provision)

    def test_update_config_resp(self):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {'api': False, 'roles': ['controller'],
                 'status': consts.NODE_STATUSES.deploying},
                {'api': False, 'roles': ['compute'],
                 'status': consts.NODE_STATUSES.deploying},
            ])

        nodes = self.env.nodes

        task = Task(
            uuid=str(uuid.uuid4()),
            name=consts.TASK_NAMES.deployment,
            cluster_id=self.env.clusters[0].id
        )
        task.cache = {'nodes': [nodes[0].uid, nodes[1].uid]}
        self.db.add(task)
        self.db.commit()

        kwargs = {
            'task_uuid': task.uuid,
            'status': consts.TASK_STATUSES.ready,
            'progress': 100
        }
        self.receiver.update_config_resp(**kwargs)
        self.db.refresh(nodes[0])
        self.db.refresh(nodes[1])
        self.db.refresh(task)

        self.assertEqual(nodes[0].status, consts.NODE_STATUSES.ready)
        self.assertEqual(nodes[1].status, consts.NODE_STATUSES.ready)
        self.assertEqual(task.status, consts.TASK_STATUSES.ready)

    def _check_success_message(self, callback, task_name, c_status, n_status):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {'api': False, 'roles': ['controller'],
                 'status': consts.NODE_STATUSES.discover},
                {'api': False, 'roles': ['compute'],
                 'status': consts.NODE_STATUSES.discover},
            ])
        cluster = self.env.clusters[-1]
        nodes = self.env.nodes
        task_title = task_name.title()
        task = Task(
            uuid=str(uuid.uuid4()),
            name=task_name,
            cluster_id=cluster.id
        )
        task.cache = {'nodes': [nodes[0].uid, nodes[1].uid]}
        self.db.add(task)
        self.db.flush()
        params = {
            'task_uuid': task.uuid,
            'status': consts.TASK_STATUSES.ready,
            'progress': 100,
            'nodes': [{'uid': nodes[0].uid, 'status': n_status}]
        }
        callback(**params)
        self.assertEqual(
            "{0} of 1 environment node(s) is done.".format(task_title),
            task.message
        )
        self.db.refresh(cluster)
        self.assertEqual(consts.CLUSTER_STATUSES.partial_deploy, cluster.status)
        params['nodes'] = []
        callback(**params)
        self.assertEqual(
            "{0} is done. No changes.".format(task_title),
            task.message
        )
        params['nodes'] = [{'uid': nodes[1].uid, 'status': n_status}]
        callback(**params)
        self.assertEqual(
            "{0} of environment '{1}' is done."
            .format(task_title, cluster.name),
            task.message
        )
        self.db.refresh(cluster)
        self.assertEqual(c_status, cluster.status)

    def test_success_deploy_messsage(self):
        self._check_success_message(
            self.receiver.deploy_resp,
            consts.TASK_NAMES.deployment,
            consts.CLUSTER_STATUSES.operational,
            consts.NODE_STATUSES.ready
        )

    def test_success_provision_messsage(self):
        self._check_success_message(
            self.receiver.deploy_resp,
            consts.TASK_NAMES.provision,
            consts.CLUSTER_STATUSES.partial_deploy,
            consts.NODE_STATUSES.provisioned
        )


class TestResetEnvironment(BaseReciverTestCase):

    @mock.patch('nailgun.rpc.receiver.logs_utils.delete_node_logs')
    def test_delete_logs_after_reset(self, mock_delete_logs):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"api": False, "status": consts.NODE_STATUSES.ready},
            ]
        )
        cluster = self.env.clusters[0]

        node = self.env.nodes[0]

        task = Task(
            uuid=str(uuid.uuid4()),
            name=consts.TASK_NAMES.reset_environment,
            cluster_id=cluster.id)
        self.db.add(task)
        self.db.flush()

        resp = {
            'task_uuid': task.uuid,
            'status': consts.TASK_STATUSES.ready,
            'nodes': [
                {'uid': node.uid},
            ]
        }
        self.receiver.reset_environment_resp(**resp)
        mock_delete_logs.assert_called_once_with(node)
