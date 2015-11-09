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
import gzip
import os
import shutil
import tempfile
import time

import mock

from oslo_serialization import jsonutils

import nailgun
from nailgun.api.v1.handlers.logs import BaseLogParser
from nailgun.api.v1.handlers.logs import LogParser
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
        node_ip = '40.30.20.10'
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
        log_parser = LogParser(f)

        forward_lines = []
        backward_lines = []

        # test empty files
        forward_lines = list(f)
        backward_lines = list(log_parser._read_backwards(f))
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
            backward_lines = list(
                log_parser._read_backwards(f, bufsize=bufsize))
            backward_lines.reverse()
            self.assertEqual(forward_lines, backward_lines)

            # test partial file reading from middle to beginning
            forward_lines = []
            for i in range(2 * len(contents)):
                forward_lines.append(f.readline())
            backward_lines = list(
                log_parser._read_backwards(
                    f, from_byte=f.tell(), bufsize=bufsize)
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
                    list(log_parser._read_backwards(
                        f, from_byte=from_byte, bufsize=bufsize)),
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

    def _create_logrotated_logfile_for_node(
            self, log_config, log_entries, node=None):
        if log_config['remote']:
            log_dir = os.path.join(self.log_dir, node.ip)
            not os.path.isdir(log_dir) and os.makedirs(log_dir)
            log_file = os.path.join(log_dir, log_config['path'])
        else:
            log_file = log_config['path']
        log_file = '{0}.1.gz'.format(log_file)
        f = gzip.open(log_file, 'wb')
        for log_entry in log_entries:
            f.write(self._format_log_entry(log_entry))
            f.flush()
        f.close()

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
        self.assertRaises(errors.DumpRunning, tm.execute)

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
            raise errors.DumpRunning()

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


class TestBaseLogParser(BaseIntegrationTest):

    def test_init(self):
        log_file = '/foo/bar/baz'
        fetch_older = True
        max_entries = 100
        log_config = {'foo': 'bar'}
        regexp = '.*'
        level = 'DEBUG'
        log_parser = BaseLogParser(
            log_file, fetch_older=fetch_older, max_entries=max_entries,
            log_config=log_config, regexp=regexp, level=level)

        self.assertEqual(log_parser.log_file, log_file)
        self.assertEqual(log_parser.fetch_older, fetch_older)
        self.assertEqual(log_parser.max_entries, max_entries)
        self.assertEqual(log_parser.log_config, log_config)
        self.assertEqual(log_parser.regexp, regexp)
        self.assertEqual(log_parser.level, level)


class TestLogParser(BaseIntegrationTest):

    def test_init(self):
        log_file = '/foo/bar/baz'
        fetch_older = True
        max_entries = 100
        log_config = {'foo': 'bar'}
        regexp = '.*'
        level = 'DEBUG'
        log_parser = BaseLogParser(
            log_file, fetch_older=fetch_older, max_entries=max_entries,
            log_config=log_config, regexp=regexp, level=level)

        self.assertEqual(log_parser.log_file, log_file)
        self.assertEqual(log_parser.fetch_older, fetch_older)
        self.assertEqual(log_parser.max_entries, max_entries)
        self.assertEqual(log_parser.log_config, log_config)
        self.assertEqual(log_parser.regexp, regexp)
        self.assertEqual(log_parser.level, level)


class BaseTestLogParsingStrategy(BaseIntegrationTest):

    def setUp(self):
        super(BaseTestLogParsingStrategy, self).setUp()
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
        super(BaseTestLogParsingStrategy, self).tearDown()

    def _format_log_entry(self, log_entry):
        return ':'.join(log_entry) + '\n'

    def _write_logfile(self, log_entries):
        log_file = settings.LOGS[0]['path']
        with open(log_file, 'a') as f:
            for log_entry in log_entries:
                f.write(self._format_log_entry(log_entry))
                f.flush()

    def _create_gzip_logfile(self, log_entries, number=1):
        log_file = settings.LOGS[0]['path']
        log_file = '{0}.{1}.gz'.format(log_file, number)
        f = gzip.open(log_file, 'wb')
        for log_entry in log_entries:
            f.write(self._format_log_entry(log_entry))
            f.flush()
        f.close()

    def _create_and_populate_logfile(self, count):
        entries = []
        for i in range(count):
            entries.append(self._create_log_entry(count + 1, count + 1))
        self._write_logfile(entries)
        return entries

    def _create_log_entry(self, level, text):
        return [
            time.strftime(settings.UI_LOG_DATE_FORMAT),
            'LEVEL{0}'.format(level),
            'text{0}'.format(text)]

    def _create_and_populate_logfiles(self, counts):
        result = []
        for cid, count in enumerate(counts):
            entries = []
            for c in range(count):
                entry = [
                    time.strftime(settings.UI_LOG_DATE_FORMAT),
                    'LEVEL{0}{1}'.format(cid + 1, c + 1),
                    'text{0}{1}'.format(cid + 1, c + 1),
                ]
                entries.append(entry)
            if cid:
                self._create_gzip_logfile(entries, cid)
            else:
                self._write_logfile(entries)
            result.append(entries)
        return result

    def _rotate_log_file(self, with_temp_file=False):
        base_filename = settings.LOGS[0]['path']
        numbered_filename = None
        gzip_filename = None
        for i in range(1, 100):
            numbered_filename = '{0}.{1}'.format(base_filename, i)
            gzip_filename = '{0}.{1}.gz'.format(base_filename, i)
            if not os.path.exists(gzip_filename):
                break
        shutil.move(base_filename, numbered_filename)
        open(base_filename, 'a').close()
        with open(numbered_filename) as src:
            buffer_size = 1024 * 1024
            dst = gzip.open(gzip_filename, 'wb')
            while True:
                copy_buffer = src.read(buffer_size)
                if not copy_buffer:
                    break
                dst.write(copy_buffer)
            dst.close()
        if not with_temp_file:
            os.remove(numbered_filename)


class TestTailLogParsingStrategy(BaseTestLogParsingStrategy):

    def test_base_log_with_less_entries_then_max_entries(self):
        self.env.create_cluster(api=False)
        entries = self._create_and_populate_logfile(10)

        resp = self.app.get(
            reverse('LogEntryCollectionHandler'),
            params={'source': settings.LOGS[0]['id'],
                    'max_entries': 20},
            headers=self.default_headers)

        self.assertEqual(resp.status_code, 200)
        response = resp.json_body
        self.assertEqual(len(response['entries']), 10)
        self.assertEqual(
            list(reversed(entries)), response['entries'])
        self.assertEqual(response['from'], 0)
        self.assertEqual(
            response['to'],
            len(''.join(map(self._format_log_entry, entries))))

    def test_base_log_with_equal_entries_to_max_entries(self):
        self.env.create_cluster(api=False)
        entries = self._create_and_populate_logfile(10)

        resp = self.app.get(
            reverse('LogEntryCollectionHandler'),
            params={'source': settings.LOGS[0]['id'],
                    'max_entries': 10},
            headers=self.default_headers)

        self.assertEqual(resp.status_code, 200)
        response = resp.json_body
        self.assertEqual(len(response['entries']), 10)
        self.assertEqual(
            list(reversed(entries)), response['entries'])
        self.assertEqual(response['from'], 0)
        self.assertEqual(
            response['to'],
            len(''.join(map(self._format_log_entry, entries))))

    def test_base_log_fetch_with_max_entries(self):
        self.env.create_cluster(api=False)
        entries = self._create_and_populate_logfile(100)
        expected_entries = entries[80:]
        total_len = len(''.join(map(self._format_log_entry, entries)))
        from_byte = total_len - len(
            ''.join(map(self._format_log_entry, expected_entries)))

        resp = self.app.get(
            reverse('LogEntryCollectionHandler'),
            params={'source': settings.LOGS[0]['id'],
                    'max_entries': 20},
            headers=self.default_headers)

        self.assertEqual(resp.status_code, 200)
        response = resp.json_body
        self.assertEqual(len(response['entries']), 20)
        self.assertEqual(len(response['entries']), len(expected_entries))
        self.assertEqual(
            list(reversed(entries[80:])), response['entries'])
        self.assertEqual(response['from'], from_byte)
        self.assertEqual(response['to'], total_len)

    def test_log_rotated_fetch_all(self):
        self.env.create_cluster(api=False)
        entries = self._create_and_populate_logfiles([20, 80])
        expected_entries = (
            list(reversed(entries[0])) + list(reversed(entries[1])))
        total_len = len(''.join(map(self._format_log_entry, expected_entries)))

        resp = self.app.get(
            reverse('LogEntryCollectionHandler'),
            params={'source': settings.LOGS[0]['id'],
                    'max_entries': 100},
            headers=self.default_headers)

        self.assertEqual(resp.status_code, 200)
        response = resp.json_body
        self.assertEqual(len(response['entries']), 100)
        self.assertEqual(len(response['entries']), len(expected_entries))
        self.assertEqual(
            list(expected_entries), response['entries'])
        self.assertEqual(response['from'], 0)
        self.assertEqual(response['to'], total_len)

    def test_log_rotated_partial_fetch_from_base_only(self):
        self.env.create_cluster(api=False)
        entries = self._create_and_populate_logfiles([20, 80])
        expected_entries = list(reversed(entries[0]))[:10]

        total_len = len(
            ''.join(map(self._format_log_entry, entries[0] + entries[1])))
        from_byte = total_len - len(
            ''.join(map(self._format_log_entry, expected_entries)))

        resp = self.app.get(
            reverse('LogEntryCollectionHandler'),
            params={'source': settings.LOGS[0]['id'],
                    'max_entries': 10},
            headers=self.default_headers)

        self.assertEqual(resp.status_code, 200)
        response = resp.json_body
        self.assertEqual(len(response['entries']), len(expected_entries))
        self.assertEqual(
            list(expected_entries), response['entries'])
        self.assertEqual(response['from'], from_byte)
        self.assertEqual(response['to'], total_len)

    def test_log_rotated_partial_fetch_from_logrotated(self):
        self.env.create_cluster(api=False)
        entries = self._create_and_populate_logfiles([20, 40, 40])
        expected_entries = (
            list(reversed(entries[0])) +
            list(reversed(entries[1])) +
            list(reversed(entries[2]))[:10])

        total_len = len(
            ''.join(map(
                self._format_log_entry, entries[0] + entries[1] + entries[2])))
        from_byte = total_len - len(
            ''.join(map(self._format_log_entry, expected_entries)))

        resp = self.app.get(
            reverse('LogEntryCollectionHandler'),
            params={'source': settings.LOGS[0]['id'],
                    'max_entries': 70},
            headers=self.default_headers)

        self.assertEqual(resp.status_code, 200)
        response = resp.json_body
        self.assertEqual(len(response['entries']), len(expected_entries))
        self.assertEqual(response['entries'], list(expected_entries))
        self.assertEqual(response['from'], from_byte)
        self.assertEqual(response['to'], total_len)

    def test_log_rotated_partial_fetch_when_base_is_empty(self):
        self.env.create_cluster(api=False)
        entries = self._create_and_populate_logfiles([0, 40, 40])
        expected_entries = list(reversed(entries[1]))[:10]

        total_len = len(
            ''.join(map(
                self._format_log_entry, entries[0] + entries[1] + entries[2])))
        from_byte = total_len - len(
            ''.join(map(self._format_log_entry, expected_entries)))

        resp = self.app.get(
            reverse('LogEntryCollectionHandler'),
            params={'source': settings.LOGS[0]['id'],
                    'max_entries': 10},
            headers=self.default_headers)

        self.assertEqual(resp.status_code, 200)
        response = resp.json_body
        self.assertEqual(len(response['entries']), len(expected_entries))
        self.assertEqual(response['entries'], list(expected_entries))
        self.assertEqual(response['from'], from_byte)
        self.assertEqual(response['to'], total_len)


class TestDiffLogParsingStrategy(BaseTestLogParsingStrategy):

    def test_diff_most_often_case(self):
        self.env.create_cluster(api=False)
        entries = self._create_and_populate_logfile(100)
        expected_entries = list(reversed(entries))[:10]
        total_len = len(
            ''.join(map(self._format_log_entry, entries)))
        from_byte = total_len - len(
            ''.join(map(self._format_log_entry, expected_entries)))

        resp = self.app.get(
            reverse('LogEntryCollectionHandler'),
            params={'source': settings.LOGS[0]['id'],
                    'max_entries': 10},
            headers=self.default_headers)

        self.assertEqual(resp.status_code, 200)
        response = resp.json_body
        self.assertEqual(len(response['entries']), len(expected_entries))
        self.assertEqual(response['entries'], expected_entries)
        self.assertEqual(response['from'], from_byte)
        self.assertEqual(response['to'], total_len)

        resp = self.app.get(
            reverse('LogEntryCollectionHandler'),
            params={'source': settings.LOGS[0]['id'],
                    'from': response['from'],
                    'to': response['to']},
            headers=self.default_headers)

        self.assertEqual(resp.status_code, 200)
        repetitive_response = resp.json_body
        self.assertEqual(repetitive_response['entries'], [])
        self.assertEqual(repetitive_response['from'], response['from'])
        self.assertEqual(repetitive_response['to'], response['to'])

        new_log_entries = [self._create_log_entry('FOO', 'bar'), ]
        self._write_logfile(new_log_entries)
        new_log_entries_len = len(
            ''.join(map(self._format_log_entry, new_log_entries)))

        resp = self.app.get(
            reverse('LogEntryCollectionHandler'),
            params={'source': settings.LOGS[0]['id'],
                    'from': response['from'],
                    'to': response['to']},
            headers=self.default_headers)

        self.assertEqual(resp.status_code, 200)
        response = resp.json_body
        self.assertEqual(response['entries'], new_log_entries)
        self.assertEqual(response['from'], repetitive_response['from'])
        self.assertEqual(response['to'], total_len + new_log_entries_len)

    def test_log_rotate_recently_added_only_in_base_log(self):
        self.env.create_cluster(api=False)
        entries = self._create_and_populate_logfile(100)
        expected_entries = list(reversed(entries))[:10]
        total_len = len(
            ''.join(map(self._format_log_entry, entries)))
        from_byte = total_len - len(
            ''.join(map(self._format_log_entry, expected_entries)))

        resp = self.app.get(
            reverse('LogEntryCollectionHandler'),
            params={'source': settings.LOGS[0]['id'],
                    'max_entries': 10},
            headers=self.default_headers)

        self.assertEqual(resp.status_code, 200)
        response = resp.json_body
        self.assertEqual(len(response['entries']), len(expected_entries))
        self.assertEqual(response['entries'], expected_entries)
        self.assertEqual(response['from'], from_byte)
        self.assertEqual(response['to'], total_len)

        self._rotate_log_file()

        new_log_entries = [self._create_log_entry('ENTRY1', 'entry1'),
                           self._create_log_entry('ENTRY2', 'entry2'),
                           self._create_log_entry('ENTRY3', 'entry3')]
        self._write_logfile(new_log_entries)
        new_log_entries_len = len(
            ''.join(map(self._format_log_entry, new_log_entries)))

        resp = self.app.get(
            reverse('LogEntryCollectionHandler'),
            params={'source': settings.LOGS[0]['id'],
                    'from': response['from'],
                    'to': response['to']},
            headers=self.default_headers)

        self.assertEqual(resp.status_code, 200)
        new_response = resp.json_body
        self.assertEqual(len(new_response['entries']), len(new_log_entries))
        self.assertEqual(
            new_response['entries'], list(reversed(new_log_entries)))
        self.assertEqual(new_response['from'], response['from'])
        self.assertEqual(new_response['to'], total_len + new_log_entries_len)


class TestFetchOlderLogParsingStrategy(BaseTestLogParsingStrategy):

    def test_fetch_from_base_log_only(self):
        self.env.create_cluster(api=False)
        entries = self._create_and_populate_logfile(100)
        expected_entries = list(reversed(entries))[:10]
        total_len = len(
            ''.join(map(self._format_log_entry, entries)))
        from_byte = total_len - len(
            ''.join(map(self._format_log_entry, expected_entries)))

        resp = self.app.get(
            reverse('LogEntryCollectionHandler'),
            params={'source': settings.LOGS[0]['id'],
                    'max_entries': 10},
            headers=self.default_headers)

        self.assertEqual(resp.status_code, 200)
        response = resp.json_body
        self.assertEqual(len(response['entries']), len(expected_entries))
        self.assertEqual(response['entries'], expected_entries)
        self.assertEqual(response['from'], from_byte)
        self.assertEqual(response['to'], total_len)

        resp = self.app.get(
            reverse('LogEntryCollectionHandler'),
            params={'source': settings.LOGS[0]['id'],
                    'fetch_older': True,
                    'from': response['from'],
                    'max_entries': 10},
            headers=self.default_headers)

        expected_entries = list(reversed(entries))[10:20]
        from_byte = from_byte - len(
            ''.join(map(self._format_log_entry, expected_entries)))

        self.assertEqual(resp.status_code, 200)
        response = resp.json_body
        self.assertEqual(len(response['entries']), len(expected_entries))
        self.assertEqual(response['entries'], expected_entries)
        self.assertEqual(response['from'], from_byte)
        self.assertEqual(response['to'], total_len)

        resp = self.app.get(
            reverse('LogEntryCollectionHandler'),
            params={'source': settings.LOGS[0]['id'],
                    'fetch_older': True,
                    'from': response['from'],
                    'max_entries': 10},
            headers=self.default_headers)

        expected_entries = list(reversed(entries))[20:30]
        from_byte = from_byte - len(
            ''.join(map(self._format_log_entry, expected_entries)))

        self.assertEqual(resp.status_code, 200)
        response = resp.json_body
        self.assertEqual(len(response['entries']), len(expected_entries))
        self.assertEqual(response['entries'], expected_entries)
        self.assertEqual(response['from'], from_byte)
        self.assertEqual(response['to'], total_len)

    def test_fetch_from_base_log_and_logrotated(self):
        self.env.create_cluster(api=False)
        entries = self._create_and_populate_logfiles([20, 40, 40])
        expected_entries = list(reversed(entries[0]))[:10]
        total_len = len(
            ''.join(map(
                self._format_log_entry, entries[0] + entries[1] + entries[2])))
        from_byte = total_len - len(
            ''.join(map(self._format_log_entry, expected_entries)))

        resp = self.app.get(
            reverse('LogEntryCollectionHandler'),
            params={'source': settings.LOGS[0]['id'],
                    'max_entries': 10},
            headers=self.default_headers)

        self.assertEqual(resp.status_code, 200)
        response = resp.json_body
        self.assertEqual(len(response['entries']), len(expected_entries))
        self.assertEqual(response['entries'], expected_entries)
        self.assertEqual(response['from'], from_byte)
        self.assertEqual(response['to'], total_len)

        resp = self.app.get(
            reverse('LogEntryCollectionHandler'),
            params={'source': settings.LOGS[0]['id'],
                    'fetch_older': True,
                    'from': response['from'],
                    'max_entries': 10},
            headers=self.default_headers)

        expected_entries = list(reversed(entries[0]))[10:20]
        from_byte = from_byte - len(
            ''.join(map(self._format_log_entry, expected_entries)))

        self.assertEqual(resp.status_code, 200)
        response = resp.json_body
        self.assertEqual(len(response['entries']), len(expected_entries))
        self.assertEqual(response['entries'], expected_entries)
        self.assertEqual(response['from'], from_byte)
        self.assertEqual(response['to'], total_len)

        resp = self.app.get(
            reverse('LogEntryCollectionHandler'),
            params={'source': settings.LOGS[0]['id'],
                    'fetch_older': True,
                    'from': response['from'],
                    'max_entries': 10},
            headers=self.default_headers)

        expected_entries = list(reversed(entries[1]))[:10]
        from_byte = from_byte - len(
            ''.join(map(self._format_log_entry, expected_entries)))

        self.assertEqual(resp.status_code, 200)
        response = resp.json_body
        self.assertEqual(len(response['entries']), len(expected_entries))
        self.assertEqual(response['entries'], expected_entries)
        self.assertEqual(response['from'], from_byte)
        self.assertEqual(response['to'], total_len)

        resp = self.app.get(
            reverse('LogEntryCollectionHandler'),
            params={'source': settings.LOGS[0]['id'],
                    'fetch_older': True,
                    'from': response['from'],
                    'max_entries': 20},
            headers=self.default_headers)

        expected_entries = list(reversed(entries[1]))[10:30]
        from_byte = from_byte - len(
            ''.join(map(self._format_log_entry, expected_entries)))

        self.assertEqual(resp.status_code, 200)
        response = resp.json_body

        self.assertEqual(len(response['entries']), len(expected_entries))
        self.assertEqual(response['entries'], expected_entries)
        self.assertEqual(response['from'], from_byte)
        self.assertEqual(response['to'], total_len)

        resp = self.app.get(
            reverse('LogEntryCollectionHandler'),
            params={'source': settings.LOGS[0]['id'],
                    'fetch_older': True,
                    'from': response['from'],
                    'max_entries': 20},
            headers=self.default_headers)

        expected_entries = (
            list(reversed(entries[1]))[30:40] +
            list(reversed(entries[2]))[:10])
        from_byte = from_byte - len(
            ''.join(map(self._format_log_entry, expected_entries)))

        self.assertEqual(resp.status_code, 200)
        response = resp.json_body

        self.assertEqual(len(response['entries']), len(expected_entries))
        self.assertEqual(response['entries'], expected_entries)
        self.assertEqual(response['from'], from_byte)
        self.assertEqual(response['to'], total_len)
