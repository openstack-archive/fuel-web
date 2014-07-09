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

import os
import shutil
import tempfile
import time

from mock import Mock
from mock import patch

import nailgun
from nailgun.api.v1.handlers.logs import read_backwards
from nailgun.db.sqlalchemy.models import Role
from nailgun.errors import errors
from nailgun.openstack.common import jsonutils
from nailgun.settings import settings
from nailgun.task.manager import DumpTaskManager
from nailgun.task.task import DumpTask
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks
from nailgun.test.base import reverse


class TestLogs(BaseIntegrationTest):

    def setUp(self):
        super(TestLogs, self).setUp()
        self.log_dir = tempfile.mkdtemp()
        self.local_log_file = os.path.join(self.log_dir, 'nailgun.log')
        regexp = (r'^(?P<date>\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}):'
                  '(?P<level>\w+):(?P<text>.+)$')
        settings.update({
            'LOGS': [
                {
                    'id': 'nailgun',
                    'name': 'Nailgun',
                    'remote': False,
                    'regexp': regexp,
                    'date_format': settings.UI_LOG_DATE_FORMAT,
                    'levels': [],
                    'path': self.local_log_file
                }, {
                    'id': 'syslog',
                    'name': 'Syslog',
                    'remote': True,
                    'regexp': regexp,
                    'date_format': settings.UI_LOG_DATE_FORMAT,
                    'base': self.log_dir,
                    'levels': [],
                    'path': 'test-syslog.log'
                }
            ]
        })

    def tearDown(self):
        shutil.rmtree(self.log_dir)
        super(TestLogs, self).tearDown()

    def test_log_source_collection_handler(self):
        resp = self.app.get(
            reverse('LogSourceCollectionHandler'),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        response = jsonutils.loads(resp.body)
        self.assertEqual(response, settings.LOGS)

    def test_log_source_by_node_collection_handler(self):
        node_ip = '40.30.20.10'
        node = self.env.create_node(api=False, ip=node_ip)

        resp = self.app.get(
            reverse('LogSourceByNodeCollectionHandler',
                    kwargs={'node_id': node.id}),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        response = jsonutils.loads(resp.body)
        self.assertEqual(response, [])

        log_entry = ['date111', 'level222', 'text333']
        self._create_logfile_for_node(settings.LOGS[1], [log_entry], node)
        resp = self.app.get(
            reverse('LogSourceByNodeCollectionHandler',
                    kwargs={'node_id': node.id}),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        response = jsonutils.loads(resp.body)
        self.assertEqual(response, [settings.LOGS[1]])

    def test_log_entry_collection_handler(self):
        node_ip = '10.20.30.40'
        log_entries = [
            [
                time.strftime(settings.UI_LOG_DATE_FORMAT),
                'LEVEL111',
                'text1',
            ],
            [
                time.strftime(settings.UI_LOG_DATE_FORMAT),
                'LEVEL222',
                'text2',
            ],
        ]
        cluster = self.env.create_cluster(api=False)
        node = self.env.create_node(cluster_id=cluster.id, ip=node_ip)
        self._create_logfile_for_node(settings.LOGS[0], log_entries)
        self._create_logfile_for_node(settings.LOGS[1], log_entries, node)

        resp = self.app.get(
            reverse('LogEntryCollectionHandler'),
            params={'source': settings.LOGS[0]['id']},
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        response = jsonutils.loads(resp.body)
        response['entries'].reverse()
        self.assertEqual(response['entries'], log_entries)

        resp = self.app.get(
            reverse('LogEntryCollectionHandler'),
            params={'node': node.id, 'source': settings.LOGS[1]['id']},
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        response = jsonutils.loads(resp.body)
        response['entries'].reverse()
        self.assertEqual(response['entries'], log_entries)

    def test_multiline_log_entry(self):
        settings.LOGS[0]['multiline'] = True
        log_entries = [
            [
                time.strftime(settings.UI_LOG_DATE_FORMAT),
                'LEVEL111',
                'text1',
            ],
            [
                time.strftime(settings.UI_LOG_DATE_FORMAT),
                'LEVEL222',
                'text\nmulti\nline',
            ],
            [
                time.strftime(settings.UI_LOG_DATE_FORMAT),
                'LEVEL333',
                'text3',
            ],
        ]
        self.env.create_cluster(api=False)
        self._create_logfile_for_node(settings.LOGS[0], log_entries)

        resp = self.app.get(
            reverse('LogEntryCollectionHandler'),
            params={'source': settings.LOGS[0]['id']},
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        response = jsonutils.loads(resp.body)
        response['entries'].reverse()
        self.assertEqual(response['entries'], log_entries)
        settings.LOGS[0]['multiline'] = False

    def test_backward_reader(self):
        f = tempfile.TemporaryFile(mode='r+')
        forward_lines = []
        backward_lines = []

        # test empty files
        forward_lines = list(f)
        backward_lines = list(read_backwards(f))
        backward_lines.reverse()
        self.assertEqual(forward_lines, backward_lines)

        # filling file with content
        contents = [
            'Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do',
            'eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut',
            'enim ad minim veniam, quis nostrud exercitation ullamco laboris',
            'nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor',
            'in reprehenderit in voluptate velit esse cillum dolore eu fugiat',
            'nulla pariatur. Excepteur sint occaecat cupidatat non proident,',
            'sunt in culpa qui officia deserunt mollit anim id est laborum.',
        ]
        for i in range(5):
            for line in contents:
                f.write('%s\n' % line)

        # test with different buffer sizes
        for bufsize in (1, 5000):
            f.seek(0)

            # test full file reading
            forward_lines = list(f)
            backward_lines = list(read_backwards(f, bufsize))
            backward_lines.reverse()
            self.assertEqual(forward_lines, backward_lines)

            # test partial file reading from middle to beginning
            forward_lines = []
            for i in range(2 * len(contents)):
                forward_lines.append(f.readline())
            backward_lines = list(read_backwards(f, bufsize))
            backward_lines.reverse()
            self.assertEqual(forward_lines, backward_lines)

        f.close()

    def _create_logfile_for_node(self, log_config, log_entries, node=None):
        if log_config['remote']:
            log_dir = os.path.join(self.log_dir, node.ip)
            not os.path.isdir(log_dir) and os.makedirs(log_dir)
            log_file = os.path.join(log_dir, log_config['path'])
        else:
            log_file = log_config['path']
        with open(log_file, 'w') as f:
            for log_entry in log_entries:
                f.write(':'.join(log_entry) + '\n')
                f.flush()

    @patch.dict('nailgun.task.task.settings.DUMP',
                {
                    'dump': {
                        'local': {
                            'hosts': [],
                            'objects': [],
                        },
                        'master': {
                            'hosts': [],
                            'objects': [{
                                'type': 'subs',
                                'path': '/var/log/remote',
                                'subs': {}
                            }],
                        },
                        'slave': {
                            'hosts': [],
                            'objects': [],
                        }
                    },
                })
    def test_snapshot_conf(self):
        self.env.create_node(
            status='ready',
            name='node1',
            fqdn='node1.domain.tld'
        )
        conf = {
            'dump': {
                'local': {
                    'hosts': [],
                    'objects': [],
                },
                'master': {
                    'hosts': [],
                    'objects': [{
                        'type': 'subs',
                        'path': '/var/log/remote',
                        'subs': {}
                    }],
                },
                'slave': {
                    'hosts': [{
                        'address': 'node1.domain.tld',
                        'ssh-key': '/root/.ssh/id_rsa',
                    }],
                    'objects': [],
                },
            },
        }
        self.datadiff(DumpTask.conf(), conf)

    @patch.dict('nailgun.task.task.settings.DUMP', {'lastdump': 'LASTDUMP'})
    @fake_tasks(fake_rpc=False, mock_rpc=False)
    @patch('nailgun.rpc.cast')
    def test_snapshot_cast(self, mocked_rpc):
        task = self.env.create_task(name='dump')
        DumpTask.execute(task)
        message = {
            'api_version': '1',
            'method': 'dump_environment',
            'respond_to': 'dump_environment_resp',
            'args': {
                'task_uuid': task.uuid,
                'settings': DumpTask.conf()
            }
        }
        args, kwargs = nailgun.task.task.rpc.cast.call_args
        self.assertEqual(len(args), 2)
        self.datadiff(args[1], message)

    def test_snapshot_task_manager(self):
        tm = DumpTaskManager()
        mock = Mock(return_value=None)
        tm._call_silently = mock
        task = tm.execute()
        mock.assert_called_once_with(task, DumpTask)

    def test_snapshot_task_manager_already_running(self):
        self.env.create_task(name="dump")
        tm = DumpTaskManager()
        self.assertRaises(errors.DumpRunning, tm.execute)

    def test_log_package_handler_ok(self):
        task = jsonutils.dumps({
            "status": "running",
            "name": "dump",
            "progress": 0,
            "message": None,
            "id": 1,
            "uuid": "00000000-0000-0000-0000-000000000000"
        })
        tm_patcher = patch('nailgun.api.v1.handlers.logs.DumpTaskManager')
        th_patcher = patch('nailgun.api.v1.handlers.logs.objects.Task')
        tm_mocked = tm_patcher.start()
        th_mocked = th_patcher.start()
        tm_instance = tm_mocked.return_value
        tm_instance.execute.return_value = task
        th_mocked.to_json.side_effect = lambda x: x
        resp = self.app.put(
            reverse('LogPackageHandler'), "[]", headers=self.default_headers
        )
        tm_patcher.stop()
        th_patcher.stop()
        self.assertEqual(task, resp.body)
        self.assertEqual(resp.status_code, 202)

    def test_log_package_handler_failed(self):
        tm_patcher = patch('nailgun.api.v1.handlers.logs.DumpTaskManager')
        tm_mocked = tm_patcher.start()
        tm_instance = tm_mocked.return_value

        def raiser():
            raise Exception()

        tm_instance.execute.side_effect = raiser
        resp = self.app.put(
            reverse('LogPackageHandler'), "[]",
            headers=self.default_headers,
            expect_errors=True
        )
        tm_patcher.stop()
        self.assertEqual(resp.status_code, 400)

    @patch('nailgun.api.v1.handlers.logs.DumpTaskManager')
    def test_log_package_handler_with_dump_task_manager_error(self,
                                                              dump_manager):
        """Test verifies that 400 status would be returned in case of errors
        with uncompleted models in session
        """

        def dump_task_with_bad_model(*args, **kwargs):
            self.db.add(Role())
            raise errors.DumpRunning()

        dump_manager().execute.side_effect = dump_task_with_bad_model

        resp = self.app.put(
            reverse('LogPackageHandler'), "[]",
            headers=self.default_headers, expect_errors=True
        )
        self.assertEqual(resp.status_code, 400)
