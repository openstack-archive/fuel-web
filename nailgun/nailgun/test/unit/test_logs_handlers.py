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
from nailgun import errors
from nailgun.settings import settings
from nailgun.test.base import BaseAuthenticationIntegrationTest
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks
from nailgun.utils import reverse


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
        cluster = self.env.create_cluster()
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

    def test_logs_handler_with_invalid_id(self):
        resp = self.app.get(
            reverse('LogEntryCollectionHandler'),
            params={'id': 'abcd'},
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(400, resp.status_code)
