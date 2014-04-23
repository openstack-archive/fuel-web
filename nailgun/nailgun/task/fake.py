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

from itertools import chain
from itertools import repeat
from random import randrange
import re
import threading
import time

from fysom import Fysom

from kombu import Connection
from kombu import Exchange
from kombu import Queue

from nailgun import objects

from nailgun.db import db
from nailgun.db.sqlalchemy.models import Node
from nailgun.logger import logger
from nailgun.rpc.receiver import NailgunReceiver
from nailgun.settings import settings

from sqlalchemy.exc import DBAPIError

_DEADLOCK_RE_DB = re.compile(r"^.*deadlock detected.*")
_HINT_RE_DB = re.compile(r"HINT.*", flags=re.DOTALL)


def handling_db_errors(func, retries=3, **kwargs):
    try:
        func(**kwargs)
    except DBAPIError as e:
        # Retry only for deadlock error
        dbl_re = _DEADLOCK_RE_DB
        dbl_m = dbl_re.match(str(e))
        if dbl_m and retries:
            time.sleep(0.01)
            retries -= 1
            db_hint = _HINT_RE_DB.search(str(e)).group()
            logger.debug(
                "Retries %s. Deadlock error occurred. Additional info: %s",
                func.__name__,
                db_hint
            )
            handling_db_errors(func, retries=retries, **kwargs)
        else:
            raise


class FSMNodeFlow(Fysom):

    def __init__(self, data):
        super(FSMNodeFlow, self).__init__({
            'initial': 'discover',
            'events': [
                {'name': 'next',
                 'src': 'discover',
                 'dst': 'provisioning'},
                {'name': 'next',
                 'src': 'provisioning',
                 'dst': 'provisioned'},
                {'name': 'next',
                 'src': 'provisioned',
                 'dst': 'deploying'},
                {'name': 'next',
                 'src': 'deploying',
                 'dst': 'ready'},
                {'name': 'next',
                 'src': 'error',
                 'dst': 'error'},
                {
                    'name': 'error',
                    'src': [
                        'discover',
                        'provisioning',
                        'provisioned',
                        'deployment',
                        'ready',
                        'error'
                    ],
                    'dst': 'error'
                },
                {
                    'name': 'ready',
                    'src': [
                        'discover',
                        'provisioning',
                        'provisioned',
                        'deployment',
                        'ready',
                        'error'
                    ],
                    'dst': 'ready'
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
        if data.get('status') == 'error':
            self.error()
        else:
            self.next()

    def on_ready(self, e):
        self.data['status'] = 'ready'
        self.data['progress'] = 100

    def on_error(self, e):
        self.data['status'] = 'error'
        if e.src in ['discover', 'provisioning']:
            self.data['error_type'] = 'provision'
        elif e.src in ['provisioned', 'deploying', 'ready']:
            self.data['error_type'] = 'deploy'
        self.data['progress'] = 100

    def on_next(self, e):
        if e.dst in ['provisioning', 'deploying']:
            self.data['progress'] = 0
        self.data['status'] = e.dst

    def update_progress(self, value):
        self.data['progress'] += value
        if self.data['progress'] >= 100:
            self.data['progress'] = 100
            self.next()


class FakeThread(threading.Thread):
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
            receiver = NailgunReceiver
            resp_method = getattr(receiver, self.respond_to)
            for msg in self.message_gen():
                resp_method(**msg)


class FakeDeploymentThread(FakeAmpqThread):

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

    def message_gen(self):
        # TEST: we can fail at any stage:
        # "provisioning" or "deployment"
        error = self.params.get("error")
        # TEST: error message from "orchestrator"
        error_msg = self.params.get("error_msg", "")
        # TEST: we can set task to ready no matter what
        # True or False
        task_ready = self.params.get("task_ready")

        # instant deployment
        godmode = self.params.get("godmode", False)

        kwargs = {
            'task_uuid': self.task_uuid,
            'nodes': self.data['args']['deployment_info'],
            'status': 'running'
        }

        if godmode:
            for n in kwargs["nodes"]:
                n["status"] = "ready"
                n["progress"] = 100
            kwargs["status"] = "ready"
            yield kwargs
            raise StopIteration

        smart_nodes = [FSMNodeFlow(n) for n in kwargs['nodes']]

        stages_errors = {
            # no errors - default deployment
            None: chain(
                self.run_until_status(smart_nodes, 'provisioned'),
                self.run_until_status(smart_nodes, 'ready', 'controller'),
                self.run_until_status(smart_nodes, 'ready')
            ),
            # error on provisioning stage
            'provisioning': chain(
                self.run_until_status(
                    smart_nodes,
                    'provisioned',
                    random_error=True
                )
            ),
            # error on deployment stage
            'deployment': chain(
                self.run_until_status(smart_nodes, 'provisioned'),
                self.run_until_status(
                    smart_nodes,
                    'ready',
                    'controller',
                    random_error=True
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
        receiver = NailgunReceiver

        self.sleep(self.tick_interval * 2)

        # Since we just add systems to cobbler and reboot nodes
        # We think this task is always successful if it is launched.
        kwargs = {
            'task_uuid': self.task_uuid,
            'status': 'ready',
            'progress': 100
        }

        resp_method = getattr(receiver, self.respond_to)
        resp_method(**kwargs)


class FakeDeletionThread(FakeThread):
    def run(self):
        super(FakeDeletionThread, self).run()
        receiver = NailgunReceiver
        kwargs = {
            'task_uuid': self.task_uuid,
            'nodes': self.data['args']['nodes'],
            'status': 'ready'
        }
        nodes_to_restore = self.data['args'].get('nodes_to_restore', [])
        resp_method = getattr(receiver, self.respond_to)
        handling_db_errors(resp_method, **kwargs)

        recover_nodes = self.params.get("recover_nodes", True)

        if not recover_nodes:
            return

        for node_data in nodes_to_restore:
            # Offline node just deleted from db
            # and could not recreated with status
            # discover
            if "online" in node_data and not node_data["online"]:
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
        resp_method(**kwargs)

        if not recover_nodes:
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
        resp_method(**kwargs)

        if not recover_nodes:
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
        receiver = NailgunReceiver
        kwargs = {
            'task_uuid': self.task_uuid,
            'progress': 0
        }

        tick_count = int(settings.FAKE_TASKS_TICK_COUNT)
        tick_interval = int(settings.FAKE_TASKS_TICK_INTERVAL)
        low_tick_count = tick_count - 20
        if low_tick_count < 0:
            low_tick_count = 0

        resp_method = getattr(receiver, self.respond_to)
        kwargs['progress'] = 0
        timeout = 30
        timer = time.time()
        ready = False

        # some kinda hack for debugging in fake tasks:
        # verification will fail if you specified 404 as VLAN id in any net
        for n in self.data['args']['nodes']:
            for iface in n['networks']:
                if 404 in iface['vlans']:
                    iface['vlans'] = list(set(iface['vlans']) ^ set([404]))

        while not ready and not self.stoprequest.isSet():
            kwargs['progress'] += randrange(
                low_tick_count,
                tick_count
            )
            if kwargs['progress'] >= 100:
                kwargs['progress'] = 100
                kwargs['nodes'] = self.data['args']['nodes']
                kwargs['status'] = 'ready'
                ready = True
            resp_method(**kwargs)
            if time.time() - timer > timeout:
                raise Exception("Timeout exceed")
            self.sleep(tick_interval)


class FakeCheckingDhcpThread(FakeAmpqThread):
    """Thread to be used with test_task_managers.py
    """

    NODES = [{'uid': '90',
              'status': 'ready',
              'data': [{'mac': 'ee:ae:c5:e0:f5:17',
                       'server_id': '10.20.0.157',
                       'yiaddr': '10.20.0.133',
                       'iface': 'eth0'}]},
             {'uid': '91',
              'status': 'ready',
              'data': [{'mac': 'bc:ae:c5:e0:f5:85',
                        'server_id': '10.20.0.20',
                        'yiaddr': '10.20.0.131',
                        'iface': 'eth0'}]}]

    @property
    def _message(self):
        """Example of message with discovered dhcp server
        """
        return {'task_uuid': self.task_uuid,
                'error': '',
                'status': 'ready',
                'progress': 100,
                'nodes': self.NODES}

    def message_gen(self):
        self.sleep(self.tick_interval)
        if self.params.get("dhcp_error"):
            return self.error_message_gen()
        else:
            return (self._message,)


class FakeRedHatCredentials(FakeAmpqThread):
    def message_gen(self):
        self.sleep(self.tick_interval)

        error = self.params.get("error")

        redhat_info = self.data['args']['release_info']['redhat']
        if redhat_info['username'] != 'rheltest':
            self.error = "Invalid Red Hat credentials"
            return [{
                'task_uuid': self.task_uuid,
                'status': 'error',
                'progress': 100,
                'error': self.error
            }]

        if error:
            self.error = error
            return [{
                'task_uuid': self.task_uuid,
                'status': 'error',
                'progress': 100,
                'error': self.error
            }]
        else:
            return [{
                'task_uuid': self.task_uuid,
                'status': 'ready',
                'progress': 100
            }]


class FakeRedHatLicenses(FakeAmpqThread):
    def message_gen(self):
        self.sleep(self.tick_interval)
        error = self.params.get("error")

        if error:
            self.error = error
            return [{
                'task_uuid': self.task_uuid,
                'status': 'error',
                'progress': 100,
                'error': self.error
            }]
        else:
            return [{
                'task_uuid': self.task_uuid,
                'status': 'ready',
                'progress': 100,
                # for case of user warning
                #'msg': ''
            }]


class FakeRedHatUpdateCobbler(FakeAmpqThread):
    def message_gen(self):
        self.sleep(self.tick_interval)
        error = self.params.get("error")

        if error:
            self.error = error
            return [{
                'task_uuid': self.task_uuid,
                'status': 'error',
                'progress': 100,
                'error': self.error
            }]
        else:
            return [{
                'task_uuid': self.task_uuid,
                'status': 'ready',
                'progress': 100
            }]


class DownloadReleaseThread(FakeAmpqThread):
    def message_gen(self):
        kwargs = {
            'task_uuid': self.task_uuid,
            'status': 'running',
            'progress': 0,
            'release_info': self.data['args']['release_info']
        }

        ready = False
        while not ready and not self.stoprequest.isSet():
            kwargs['progress'] += randrange(
                self.low_tick_count,
                self.tick_count
            )
            if kwargs['progress'] >= 100:
                kwargs['progress'] = 100
                kwargs['status'] = 'ready'
                ready = True

            yield kwargs
            self.sleep(self.tick_interval)


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


FAKE_THREADS = {
    'provision': FakeProvisionThread,
    'deploy': FakeDeploymentThread,
    'remove_nodes': FakeDeletionThread,
    'stop_deploy_task': FakeStopDeploymentThread,
    'reset_environment': FakeResetEnvironmentThread,
    'verify_networks': FakeVerificationThread,
    'check_dhcp': FakeCheckingDhcpThread,
    'download_release': DownloadReleaseThread,
    'check_redhat_credentials': FakeRedHatCredentials,
    'check_redhat_licenses': FakeRedHatLicenses,
    'redhat_update_cobbler_profile': FakeRedHatUpdateCobbler,
    'dump_environment': FakeDumpEnvironment,
    'generate_capacity_log': FakeCapacityLog
}
