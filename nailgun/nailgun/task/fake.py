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

import copy

from itertools import chain
from itertools import repeat
from random import randrange
import threading
import time

from fysom import Fysom

from kombu import Connection
from kombu import Exchange
from kombu import Queue

from nailgun import objects

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy.models import Node
from nailgun.rpc.receiver import NailgunReceiver
from nailgun.settings import settings


class FSMNodeFlow(Fysom):

    def __init__(self, data, initial=None):
        super(FSMNodeFlow, self).__init__({
            'initial': initial or consts.NODE_STATUSES.discover,
            'events': [
                {'name': 'next',
                 'src': consts.NODE_STATUSES.discover,
                 'dst': consts.NODE_STATUSES.provisioning},
                {'name': 'next',
                 'src': consts.NODE_STATUSES.provisioning,
                 'dst': consts.NODE_STATUSES.provisioned},
                {'name': 'next',
                 'src': consts.NODE_STATUSES.provisioned,
                 'dst': consts.NODE_STATUSES.deploying},
                {'name': 'next',
                 'src': consts.NODE_STATUSES.deploying,
                 'dst': consts.NODE_STATUSES.ready},
                {'name': 'next',
                 'src': consts.NODE_STATUSES.error,
                 'dst': consts.NODE_STATUSES.error},
                {
                    'name': 'error',
                    'src': [
                        consts.NODE_STATUSES.discover,
                        consts.NODE_STATUSES.provisioning,
                        consts.NODE_STATUSES.provisioned,
                        consts.NODE_STATUSES.deploying,
                        consts.NODE_STATUSES.ready,
                        consts.NODE_STATUSES.error
                    ],
                    'dst': consts.NODE_STATUSES.error
                },
                {
                    'name': consts.NODE_STATUSES.ready,
                    'src': [
                        consts.NODE_STATUSES.discover,
                        consts.NODE_STATUSES.provisioning,
                        consts.NODE_STATUSES.provisioned,
                        consts.NODE_STATUSES.deploying,
                        consts.NODE_STATUSES.ready,
                        consts.NODE_STATUSES.error
                    ],
                    'dst': consts.NODE_STATUSES.ready
                },
            ],
            'callbacks': {
                'onnext': self.on_next,
                'onerror': self.on_error,
                'onready': self.on_ready
            }
        })
        self.data = data
        self.data.setdefault('progress', 0)
        if data.get('status') == consts.NODE_STATUSES.error:
            self.error()
        else:
            self.next()

    def on_ready(self, e):
        self.data['status'] = consts.NODE_STATUSES.ready
        self.data['progress'] = 100

    def on_error(self, e):
        self.data['status'] = consts.NODE_STATUSES.error
        if e.src in [
            consts.NODE_STATUSES.discover, consts.NODE_STATUSES.provisioning
        ]:
            self.data['error_type'] = consts.NODE_STATUSES.provision
        elif e.src in [consts.NODE_STATUSES.provisioned,
                       consts.NODE_STATUSES.deploying,
                       consts.NODE_STATUSES.ready]:
            self.data['error_type'] = 'deploy'
        self.data['progress'] = 100

    def on_next(self, e):
        if e.dst in [
            consts.NODE_STATUSES.provisioning, consts.NODE_STATUSES.deploying
        ]:
            self.data['progress'] = 0
        self.data['status'] = e.dst

    def update_progress(self, value):
        self.data['progress'] += value
        if self.data['progress'] >= 100:
            self.data['progress'] = 100
            self.next()


class FakeThread(threading.Thread):
    Receiver = NailgunReceiver

    def __init__(self, data=None, params=None, group=None, target=None,
                 name=None, verbose=None, join_to=None):
        threading.Thread.__init__(self, group=group, target=target, name=name,
                                  verbose=verbose)

        self.data = data
        self.params = params
        self.join_to = join_to
        self.tick_count = int(settings.FAKE_TASKS_TICK_COUNT)
        self.low_tick_count = self.tick_count - 10
        if self.low_tick_count < 0:
            self.low_tick_count = 0
        self.tick_interval = int(settings.FAKE_TASKS_TICK_INTERVAL)

        self.task_uuid = data['args'].get(
            'task_uuid'
        )
        self.respond_to = data['respond_to']
        self.stoprequest = threading.Event()
        self.error = None

    def run(self):
        if self.join_to:
            self.join_to.join()
            if self.join_to.error:
                self.error = "Task aborted"
                self.message_gen = self.error_message_gen

    def error_message_gen(self):
        return [{
            'task_uuid': self.task_uuid,
            'status': 'error',
            'progress': 100,
            'error': self.error
        }]

    def rude_join(self, timeout=None):
        self.stoprequest.set()
        super(FakeThread, self).join(timeout)

    def sleep(self, timeout):
        if timeout == 0:
            return

        step = 0.001

        map(
            lambda i: not self.stoprequest.isSet() and time.sleep(i),
            repeat(step, int(float(timeout) / step))
        )

    def notify(self, kwargs):
        resp_method = getattr(self.Receiver, self.respond_to)
        try:
            resp_method(**kwargs)
            db().commit()
        except Exception as e:
            # TODO(ikalnitsky): research why some tests hit this
            # code but do not fail.
            db().rollback()
            raise e

    def run_until_status(self, smart_nodes, status,
                         role=None, random_error=False,
                         instant=False):
        ready = False

        if random_error:
            smart_nodes[randrange(0, len(smart_nodes))].error()

        while not ready and not self.stoprequest.isSet():
            for sn in smart_nodes:
                continue_cases = (
                    sn.current in (status, 'error'),
                    role and (sn.data['role'] != role)
                )
                if any(continue_cases):
                    continue

                if instant:
                    sn.ready()
                else:
                    sn.update_progress(
                        randrange(
                            self.low_tick_count,
                            self.tick_count
                        )
                    )

            if role:
                test_nodes = [
                    sn for sn in smart_nodes
                    if sn.data['role'] == role
                ]
            else:
                test_nodes = smart_nodes

            node_ready_status = (
                (tn.current in (status, 'error'))
                for tn in test_nodes
            )

            if all(node_ready_status):
                ready = True

            yield [sn.data for sn in smart_nodes]


class FakeAmpqThread(FakeThread):

    def run(self):
        super(FakeAmpqThread, self).run()
        if settings.FAKE_TASKS_AMQP:
            nailgun_exchange = Exchange(
                'nailgun',
                'topic',
                durable=True
            )
            nailgun_queue = Queue(
                'nailgun',
                exchange=nailgun_exchange,
                routing_key='nailgun'
            )
            with Connection('amqp://guest:guest@localhost//') as conn:
                with conn.Producer(serializer='json') as producer:
                    for msg in self.message_gen():
                        producer.publish(
                            {
                                "method": self.respond_to,
                                "args": msg
                            },
                            exchange=nailgun_exchange,
                            routing_key='nailgun',
                            declare=[nailgun_queue]
                        )
        else:
            for msg in self.message_gen():
                self.notify(msg)


class FakeDeploymentThread(FakeAmpqThread):
    def message_gen(self):
        # TEST: we can fail at any stage:
        # "provisioning" or "deployment"
        error = self.params.get("error")
        # TEST: error message from "orchestrator"
        error_msg = self.params.get("error_msg", "")
        # TEST: we can set task to ready no matter what
        # True or False
        task_ready = self.params.get("task_ready")

        if 'godmode' in self.params:
            raise ValueError('godmode is not supported anymore, '
                             'please use override_state instead')

        override_state = self.params.get("override_state", False)

        kwargs = {
            'task_uuid': self.task_uuid,
            'nodes': self.data['args']['deployment_info'],
            'status': 'running'
        }

        if override_state:
            progress = override_state.get("progress", 0)
            status = override_state.get("status", "running")
            for n in kwargs["nodes"]:
                n["status"] = status
                n["progress"] = progress
            kwargs["status"] = status
            yield kwargs
            raise StopIteration

        smart_nodes = [
            FSMNodeFlow(n, consts.NODE_STATUSES.provisioned)
            for n in kwargs['nodes']
        ]

        stages_errors = {
            # no errors - default deployment
            None: chain(
                self.run_until_status(
                    smart_nodes, consts.NODE_STATUSES.deploying
                ),
                self.run_until_status(
                    smart_nodes, consts.NODE_STATUSES.ready, 'controller'
                ),
                self.run_until_status(
                    smart_nodes, consts.NODE_STATUSES.ready
                )
            ),
            # error on deployment stage
            'deployment': chain(
                self.run_until_status(
                    smart_nodes, consts.NODE_STATUSES.deploying
                ),
                self.run_until_status(
                    smart_nodes, consts.NODE_STATUSES.ready,
                    'controller', random_error=True
                )
            )
        }

        mode = stages_errors[error]

        for nodes_status in mode:
            kwargs['nodes'] = nodes_status
            yield kwargs
            self.sleep(self.tick_interval)

        if not error or task_ready:
            kwargs['status'] = 'ready'
        else:
            kwargs['status'] = 'error'

        if error_msg:
            kwargs['error'] = error_msg

        yield kwargs


class FakeProvisionThread(FakeThread):
    def run(self):
        super(FakeProvisionThread, self).run()
        kwargs = {
            'task_uuid': self.task_uuid,
            'status': consts.TASK_STATUSES.running,
            'progress': 0
        }

        smart_nodes = [
            FSMNodeFlow(n, consts.NODE_STATUSES.discover)
            for n in self.data['args']['provisioning_info']['nodes']
        ]

        for nodes in self.run_until_status(
                smart_nodes, consts.NODE_STATUSES.provisioned
        ):
            kwargs['nodes'] = nodes
            if nodes[0]['status'] == consts.NODE_STATUSES.provisioned:
                kwargs['status'] = consts.TASK_STATUSES.ready
            kwargs['progress'] = nodes[0]['progress']

            self.notify(kwargs)


class FakeDeletionThread(FakeThread):
    def run(self):
        super(FakeDeletionThread, self).run()
        receiver = NailgunReceiver
        kwargs = {
            'task_uuid': self.task_uuid,
            'nodes': self.data['args']['nodes'],
            'status': 'ready'
        }
        # copy the data deeply, because we're going delete the original one
        nodes_to_restore = copy.deepcopy(
            self.data['args'].get('nodes_to_restore', []))
        resp_method = getattr(receiver, self.respond_to)
        try:
            resp_method(**kwargs)
            db().commit()
        except Exception as e:
            db().rollback()
            raise e

        recover_nodes = self.params.get("recover_nodes", True)
        recover_offline_nodes = self.params.get("recover_offline_nodes", True)

        if not recover_nodes:
            db().commit()
            return

        for node_data in nodes_to_restore:
            # We want to preserve offline nodes since in fake mode
            # it's easier to do that than add new one
            is_offline = "online" in node_data and not node_data["online"]
            if is_offline and not recover_offline_nodes:
                continue

            node_data["status"] = "discover"
            objects.Node.create(node_data)
        db().commit()


class FakeStopDeploymentThread(FakeThread):
    def run(self):
        super(FakeStopDeploymentThread, self).run()
        receiver = NailgunReceiver

        recover_nodes = self.params.get("recover_nodes", True)
        ia_nodes_count = self.params.get("ia_nodes_count", 0)

        nodes = self.data['args']['nodes']
        ia_nodes = []
        if ia_nodes_count:
            ia_nodes = nodes[0:ia_nodes_count]
            nodes = nodes[ia_nodes_count:]

        self.sleep(self.tick_interval)
        kwargs = {
            'task_uuid': self.task_uuid,
            'stop_task_uuid': self.data['args']['stop_task_uuid'],
            'nodes': nodes,
            'inaccessible_nodes': ia_nodes,
            'status': 'ready',
            'progress': 100
        }
        resp_method = getattr(receiver, self.respond_to)
        try:
            resp_method(**kwargs)
            db().commit()
        except Exception as e:
            db().rollback()
            raise e

        if not recover_nodes:
            db().commit()
            return

        nodes_db = db().query(Node).filter(
            Node.id.in_([
                n['uid'] for n in self.data['args']['nodes']
            ])
        ).all()

        for n in nodes_db:
            self.sleep(self.tick_interval)
            n.online = True
            n.status = "discover"
            db().add(n)
        db().commit()


class FakeResetEnvironmentThread(FakeThread):
    def run(self):
        super(FakeResetEnvironmentThread, self).run()
        receiver = NailgunReceiver

        recover_nodes = self.params.get("recover_nodes", True)
        ia_nodes_count = self.params.get("ia_nodes_count", 0)

        nodes = self.data['args']['nodes']
        ia_nodes = []
        if ia_nodes_count:
            ia_nodes = nodes[0:ia_nodes_count]
            nodes = nodes[ia_nodes_count:]

        self.sleep(self.tick_interval)
        kwargs = {
            'task_uuid': self.task_uuid,
            'nodes': nodes,
            'inaccessible_nodes': ia_nodes,
            'status': 'ready',
            'progress': 100
        }
        resp_method = getattr(receiver, self.respond_to)
        try:
            resp_method(**kwargs)
            db().commit()
        except Exception as e:
            db().rollback()
            raise e

        if not recover_nodes:
            db().commit()
            return

        nodes_db = db().query(Node).filter(
            Node.id.in_([
                n['uid'] for n in self.data['args']['nodes']
            ])
        ).all()

        for n in nodes_db:
            self.sleep(self.tick_interval)
            n.online = True
            n.status = "discover"
            db().add(n)
        db().commit()


class FakeVerificationThread(FakeThread):
    def run(self):
        super(FakeVerificationThread, self).run()

        # some kinda hack for debugging in fake tasks:
        # verification will fail if you specified 404 as VLAN id in any net
        for n in self.data['args']['nodes']:
            for iface in n['networks']:
                if 404 in iface['vlans']:
                    iface['vlans'] = list(set(iface['vlans']) ^ set([404]))

        # we have to execute subtasks too, just like astute does. otherwise
        # we will have "running" subtasks in the database.
        for subtask in self.data.get('subtasks', []):
            thread = FAKE_THREADS[subtask['method']](subtask, self.params)
            thread.start()
            thread.join()

        resp_method = getattr(NailgunReceiver, self.respond_to)
        try:
            resp_method(
                task_uuid=self.task_uuid,
                progress=100,
                status='ready',
                nodes=self.data['args']['nodes'],
            )
            db().commit()
        except Exception as e:
            db().rollback()
            raise e


class FakeMulticastVerifications(FakeAmpqThread):
    """Network verifications will be as single dispatcher method in naily"""

    def ready_multicast(self):
        response = {
            'task_uuid': self.task_uuid,
            'progress': 0
        }
        response['progress'] = 30
        yield response

        nodes = self.data['args']['nodes']
        nodes_uid = [node['uid'] for node in nodes]

        response['status'] = 'ready'
        response['progress'] = 100
        response['nodes'] = dict((node_uid, nodes_uid)
                                 for node_uid in nodes_uid)
        yield response

    def error1_multicast(self):
        response = {
            'task_uuid': self.task_uuid,
            'progress': 0
        }
        response['progress'] = 30
        yield response

        nodes = self.data['args']['nodes']
        # no messages from last node
        nodes_uid = [node['uid'] for node in nodes][:len(nodes) - 1]

        response['status'] = 'ready'
        response['progress'] = 100
        response['nodes'] = dict((node_uid, nodes_uid)
                                 for node_uid in nodes_uid)
        yield response

    def error2_multicast(self):
        response = {
            'task_uuid': self.task_uuid,
            'progress': 0
        }
        response['progress'] = 30
        yield response

        nodes = self.data['args']['nodes']
        nodes_uid = [node['uid'] for node in nodes]

        response['status'] = 'ready'
        response['progress'] = 100
        response['nodes'] = dict((node_uid, nodes_uid)
                                 for node_uid in nodes_uid)
        # last node did not received any messages
        response['nodes'][nodes_uid[-1]] = []
        yield response

    def message_gen(self):
        task_name = '{0}_multicast'.format(self.params.get('prefix', 'ready'))
        return getattr(self, task_name)()


class FakeCheckingDhcpThread(FakeAmpqThread):
    """Thread to be used with test_task_managers.py"""

    def _get_message(self, mac):
        """Example of message with discovered dhcp server"""
        nodes = [{'uid': '90',
                  'status': 'ready',
                  'data': [{'mac': mac,
                            'server_id': '10.20.0.20',
                            'yiaddr': '10.20.0.133',
                            'iface': 'eth0'}]},
                 {'uid': '91',
                  'status': 'ready',
                  'data': [{'mac': mac,
                            'server_id': '10.20.0.20',
                            'yiaddr': '10.20.0.131',
                            'iface': 'eth0'}]}]

        return {'task_uuid': self.task_uuid,
                'error': '',
                'status': 'ready',
                'progress': 100,
                'nodes': nodes}

    def message_gen(self):
        self.sleep(self.tick_interval)
        if self.params.get("dhcp_error"):
            return self.error_message_gen()
        elif 'rogue_dhcp_mac' in self.params:
            return (self._get_message(self.params['rogue_dhcp_mac']),)
        else:
            return (self._get_message(settings.ADMIN_NETWORK['mac']),)


class FakeDumpEnvironment(FakeAmpqThread):
    def message_gen(self):
        self.sleep(self.tick_interval)
        return [{
            'task_uuid': self.task_uuid,
            'status': 'ready',
            'progress': 100,
            'msg': '/tmp/fake_dump'
        }]


class FakeCapacityLog(FakeAmpqThread):
    def message_gen(self):
        self.sleep(self.tick_interval)
        return [{
            'task_uuid': self.task_uuid,
            'status': 'ready',
            'progress': 100,
            'msg': ''
        }]


class FakeExecuteTasksThread(FakeAmpqThread):
    def message_gen(self):
        self.sleep(self.tick_interval)
        return [{
            'task_uuid': self.task_uuid,
            'status': 'ready',
            'progress': 100
        }]


class FakeCheckRepositories(FakeAmpqThread):
    def message_gen(self):
        self.sleep(self.tick_interval)
        return [{
            "task_uuid": self.task_uuid,
            "status": "ready",
            "progress": 100,
            "nodes": [{"uid": "1", "status": 0, "out": "", "err": ""}]
        }]


class FakeTaskInOrchestrator(FakeAmpqThread):
    def message_gen(self):
        self.sleep(self.tick_interval)
        return [{'task_uuid': self.task_uuid}]


FAKE_THREADS = {
    'native_provision': FakeProvisionThread,
    'image_provision': FakeProvisionThread,
    'granular_deploy': FakeDeploymentThread,
    'deploy': FakeDeploymentThread,
    'task_deploy': FakeDeploymentThread,
    'remove_nodes': FakeDeletionThread,
    'stop_deploy_task': FakeStopDeploymentThread,
    'reset_environment': FakeResetEnvironmentThread,
    'verify_networks': FakeVerificationThread,
    'check_dhcp': FakeCheckingDhcpThread,
    'dump_environment': FakeDumpEnvironment,
    'generate_capacity_log': FakeCapacityLog,
    'multicast_verification': FakeMulticastVerifications,
    'execute_tasks': FakeExecuteTasksThread,
    'check_repositories': FakeCheckRepositories,
    'check_repositories_with_setup': FakeCheckRepositories,
    'task_in_orchestrator': FakeTaskInOrchestrator
}
