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
import os
import shutil
import tempfile
import time

import mock

from oslo_serialization import jsonutils

import nailgun
from nailgun.api.v1.handlers.logs import read_backwards
from nailgun.errors import errors
from nailgun.settings import settings
from nailgun.task.manager import DumpTaskManager
from nailgun.task.task import DumpTask
from nailgun.test.base import BaseAuthenticationIntegrationTest
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks
from nailgun.utils import reverse


class TestSnapshotDownload(BaseAuthenticationIntegrationTest):

    def test_snapshot_download_handler(self):
        headers = copy.deepcopy(self.default_headers)
        headers['X-Auth-Token'] = self.get_auth_token()
        snap_name = "fuel-snapshot-2015-06-23_11-32-13.tar.xz"

        resp = self.app.get(
            reverse('SnapshotDownloadHandler',
                    kwargs={'snapshot_name': snap_name}),
            headers=headers,
        )

        self.assertEqual(200, resp.status_code)
        self.assertEqual('/dump/' + snap_name,
                         resp.headers['X-Accel-Redirect'])

    def test_snapshot_download_handler_wo_auth(self):
        snap_name = "fuel-snapshot-2015-06-23_11-32-13.tar.xz"
        resp = self.app.get(
            reverse('SnapshotDownloadHandler',
                    kwargs={'snapshot_name': snap_name}),
            headers=self.default_headers,  # without auth token
            expect_errors=True,
        )

        self.assertEqual(401, resp.status_code)

        # It's very important to do not show X-Accel-Redirect value to
        # an unauthenticated user
        self.assertNotIn('X-Accel-Redirect', resp.headers)


class TestLogs(BaseIntegrationTest):

    def setUp(self):
        super(TestLogs, self).setUp()
        self.log_dir = tempfile.mkdtemp()
        self.local_log_file = os.path.join(self.log_dir, 'nailgun.log')
        regexp = (r'^(?P<date>\d{4}-\d{2}-\d{2}\s\d{2}:\d{2}:\d{2}):'
                  '(?P<level>\w+):(?P<text>.+)$')
        self.patcher = mock.patch.object(
            settings, 'LOGS', [
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
        )
        self.patcher.start()

    def tearDown(self):
        shutil.rmtree(self.log_dir)
        self.patcher.stop()
        super(TestLogs, self).tearDown()

    def test_log_source_collection_handler(self):
        resp = self.app.get(
            reverse('LogSourceCollectionHandler'),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)

        self.assertEqual(resp.json_body, settings.LOGS)

    def test_log_source_by_node_collection_handler(self):
        node_ip = '10.20.0.130'
        node = self.env.create_node(api=False, ip=node_ip)

        resp = self.app.get(
            reverse('LogSourceByNodeCollectionHandler',
                    kwargs={'node_id': node.id}),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        response = resp.json_body
        self.assertEqual(response, [])

        log_entry = ['date111', 'level222', 'text333']
        self._create_logfile_for_node(settings.LOGS[1], [log_entry], node)
        resp = self.app.get(
            reverse('LogSourceByNodeCollectionHandler',
                    kwargs={'node_id': node.id}),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        self.assertEqual(resp.json_body, [settings.LOGS[1]])

    def test_log_entry_collection_handler(self):
        node_ip = '10.20.0.130'
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
        self.env.create_cluster()
        cluster = self.env.clusters[0]
        node = self.env.create_node(cluster_id=cluster.id, ip=node_ip)
        self._create_logfile_for_node(settings.LOGS[0], log_entries)
        self._create_logfile_for_node(settings.LOGS[1], log_entries, node)

        resp = self.app.get(
            reverse('LogEntryCollectionHandler'),
            params={'source': settings.LOGS[0]['id']},
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        response = resp.json_body
        response['entries'].reverse()
        self.assertEqual(response['entries'], log_entries)

        resp = self.app.get(
            reverse('LogEntryCollectionHandler'),
            params={'node': node.id, 'source': settings.LOGS[1]['id']},
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        response = resp.json_body
        response['entries'].reverse()
        self.assertEqual(response['entries'], log_entries)

    def test_multiline_log_entry(self):
        # we can do this because we have patched settings in setUp
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
        response = resp.json_body
        response['entries'].reverse()
        self.assertEqual(response['entries'], log_entries)

    def test_incremental_older_fetch(self):
        """Older entries should be fetched incrementally."""
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
            [
                time.strftime(settings.UI_LOG_DATE_FORMAT),
                'LEVEL333',
                'text3',
            ],
        ]

        self.env.create_cluster(api=False)
        self._create_logfile_for_node(settings.LOGS[0], log_entries)

        total_len = len(''.join(map(self._format_log_entry, log_entries)))

        resp = self.app.get(
            reverse('LogEntryCollectionHandler'),
            params={
                'max_entries': 1,
                'source': settings.LOGS[0]['id'],
            },
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        response = resp.json_body
        self.assertEqual(response['entries'], [log_entries[2]])
        self.assertTrue(response['has_more'])
        self.assertEqual(response['to'], total_len)
        self.assertEqual(
            response['from'],
            total_len - len(self._format_log_entry(log_entries[2])))

        resp = self.app.get(
            reverse('LogEntryCollectionHandler'),
            params={
                'fetch_older': True,
                'from': response['from'],
                'to': response['to'],
                'max_entries': 1,
                'source': settings.LOGS[0]['id'],
            },
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        response = resp.json_body
        self.assertEqual(response['entries'], [log_entries[1]])
        self.assertTrue(response['has_more'])
        self.assertEqual(response['to'], total_len)
        self.assertEqual(
            response['from'],
            total_len - len(self._format_log_entry(log_entries[2])) -
            len(self._format_log_entry(log_entries[1])))

        # Normal, forward fetch shouldn't affect from and to

        resp = self.app.get(
            reverse('LogEntryCollectionHandler'),
            params={
                'fetch_older': True,
                'from': response['from'],
                'to': response['to'],
                'max_entries': 1,
                'source': settings.LOGS[0]['id'],
            },
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        response = resp.json_body
        self.assertEqual(response['entries'], [log_entries[0]])
        self.assertFalse(response['has_more'])
        self.assertEqual(response['to'], total_len)
        self.assertEqual(response['from'], 0)

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
            backward_lines = list(read_backwards(f, bufsize=bufsize))
            backward_lines.reverse()
            self.assertEqual(forward_lines, backward_lines)

            # test partial file reading from middle to beginning
            forward_lines = []
            for i in range(2 * len(contents)):
                forward_lines.append(f.readline())
            backward_lines = list(
                read_backwards(f, from_byte=f.tell(), bufsize=bufsize)
            )
            backward_lines.reverse()
            self.assertEqual(forward_lines, backward_lines)

        f.close()

        # Some special cases not caught by the tests above -- test with
        # different from_byte's
        f = tempfile.TemporaryFile(mode='r+')
        written = '\n'.join(contents)
        f.write(written)

        for from_byte in range(1, len(written)):
            lines = written[:from_byte].split('\n')
            if lines[-1] == '':
                lines = lines[:-1]
            append_newline = written[from_byte - 1] == '\n'
            if append_newline:
                lines = ['{0}\n'.format(line) for line in lines]
            else:
                lines[:-1] = ['{0}\n'.format(line) for line in lines[:-1]]

            lines = list(reversed(lines))

            for bufsize in range(1, 30):
                self.assertEqual(
                    list(read_backwards(f,
                                        from_byte=from_byte,
                                        bufsize=bufsize)),
                    lines
                )

    def _format_log_entry(self, log_entry):
        return ':'.join(log_entry) + '\n'

    def _create_logfile_for_node(self, log_config, log_entries, node=None):
        if log_config['remote']:
            log_dir = os.path.join(self.log_dir, node.ip)
            not os.path.isdir(log_dir) and os.makedirs(log_dir)
            log_file = os.path.join(log_dir, log_config['path'])
        else:
            log_file = log_config['path']
        with open(log_file, 'w') as f:
            for log_entry in log_entries:
                f.write(self._format_log_entry(log_entry))
                f.flush()

    @mock.patch.dict('nailgun.task.task.settings.DUMP', {
        'dump': {
            'local': {
                'hosts': [],
                'objects': [],
            },
            'master': {
                'hosts': [],
                'objects': [{
                    'type': 'dir',
                    'path': '/var/log/remote',
                }],
            },
            'slave': {
                'hosts': [],
                'objects': [],
            }
        },
        'target': '/path/to/save',
        'lastdump': '/path/to/latest',
        'timestamp': True,
        'compression_level': 3,
        'timeout': 60})
    def test_snapshot_conf(self):
        self.env.create_node(
            status='ready',
            hostname='node111',
            ip='10.109.0.2',
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
                        'type': 'dir',
                        'path': '/var/log/remote',
                    }],
                },
                'slave': {
                    'hosts': [{
                        'hostname': 'node111',
                        'address': '10.109.0.2',
                        'ssh-key': '/root/.ssh/id_rsa',
                        'ssh-user': 'root',
                    }],
                    'objects': [],
                },
            },
            'target': '/path/to/save',
            'lastdump': '/path/to/latest',
            'timestamp': True,
            'compression_level': 3,
            'timeout': 60,
        }
        self.datadiff(DumpTask.conf(), conf)

    @mock.patch.dict('nailgun.task.task.settings.DUMP',
                     {'lastdump': 'LASTDUMP'})
    @fake_tasks(fake_rpc=False, mock_rpc=False)
    @mock.patch('nailgun.rpc.cast')
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
        m = mock.Mock(return_value=None)
        tm._call_silently = m
        task = tm.execute()
        m.assert_called_once_with(task, DumpTask, conf=None)

    def test_snapshot_task_manager_already_running(self):
        self.env.create_task(name="dump")
        tm = DumpTaskManager()
        self.assertRaises(errors.TaskAlreadyRunning, tm.execute)

    def test_log_package_handler_ok(self):
        task = {
            "status": "running",
            "name": "dump",
            "progress": 0,
            "message": None,
            "id": 1,
            "uuid": "00000000-0000-0000-0000-000000000000"
        }
        tm_patcher = mock.patch('nailgun.api.v1.handlers.logs.DumpTaskManager')
        th_patcher = mock.patch('nailgun.api.v1.handlers.logs.objects.Task')
        tm_mocked = tm_patcher.start()
        th_mocked = th_patcher.start()
        tm_instance = tm_mocked.return_value
        tm_instance.execute.return_value = mock.Mock(**task)
        th_mocked.to_json.side_effect = lambda x: task
        resp = self.app.put(
            reverse('LogPackageHandler'), "[]", headers=self.default_headers
        )
        tm_patcher.stop()
        th_patcher.stop()
        self.assertEqual(resp.status_code, 202)
        self.assertDictEqual(task, resp.json_body)

    def test_log_package_handler_failed(self):
        tm_patcher = mock.patch('nailgun.api.v1.handlers.logs.DumpTaskManager')
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

    @mock.patch('nailgun.api.v1.handlers.logs.DumpTaskManager')
    def test_log_package_handler_with_dump_task_manager_error(self,
                                                              dump_manager):
        """400 status when errors with uncompleted models in session occur"""

        def dump_task_with_bad_model(*args, **kwargs):
            raise errors.TaskAlreadyRunning()

        dump_manager().execute.side_effect = dump_task_with_bad_model

        resp = self.app.put(
            reverse('LogPackageHandler'), "[]",
            headers=self.default_headers, expect_errors=True
        )
        self.assertEqual(resp.status_code, 400)

    @mock.patch('nailgun.task.task.DumpTask.conf')
    def test_dump_conf_returned(self, mconf):
        mconf.return_value = {'test': 'config'}
        resp = self.app.get(
            reverse('LogPackageDefaultConfig'),
            headers=self.default_headers
        )
        self.assertEqual(resp.json, {'test': 'config'})

    @mock.patch('nailgun.task.task.rpc.cast')
    def test_custom_conf_passed_to_execute(self, mcast):
        custom_config = {'test': 'config'}

        self.app.put(
            reverse('LogPackageHandler'), jsonutils.dumps(custom_config),
            headers=self.default_headers
        )

        params = mcast.call_args_list[0][0]
        self.assertEqual(params[1]['args']['settings'], custom_config)
