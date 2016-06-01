# -*- coding: utf-8 -*-
#
#    Copyright 2016 Mirantis, Inc.
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

import mock
import six
import yaml

from fuelclient.tests.unit.v2.cli import test_engine


TASKS_YAML = '''- id: custom-task-1
  type: puppet
  parameters:
    param: value
- id: custom-task-2
  type: puppet
  parameters:
    param: value
'''


class TestGraphActions(test_engine.BaseCLITest):

    @mock.patch('fuelclient.commands.graph.os')
    def _test_cmd(self, method, cmd_line, expected_kwargs, os_m):
        os_m.exists.return_value = True
        self.m_get_client.reset_mock()
        self.m_client.get_filtered.reset_mock()
        m_open = mock.mock_open(read_data=TASKS_YAML)
        with mock.patch(
                'fuelclient.cli.serializers.open', m_open, create=True):
            self.exec_command('graph {0} {1}'.format(method, cmd_line))
            self.m_get_client.assert_called_once_with('graph', mock.ANY)
            self.m_client.__getattr__(method).assert_called_once_with(
                **expected_kwargs)

    def test_upload(self):
        self._test_cmd('upload', '--env 1 --file new_graph.yaml', dict(
            data=yaml.load(TASKS_YAML),
            related_model='clusters',
            related_id=1,
            graph_type=None
        ))
        self._test_cmd('upload', '--release 1 --file new_graph.yaml', dict(
            data=yaml.load(TASKS_YAML),
            related_model='releases',
            related_id=1,
            graph_type=None
        ))
        self._test_cmd('upload', '--plugin 1 --file new_graph.yaml', dict(
            data=yaml.load(TASKS_YAML),
            related_model='plugins',
            related_id=1,
            graph_type=None
        ))
        self._test_cmd(
            'upload',
            '--plugin 1 --file new_graph.yaml --type custom_type',
            dict(
                data=yaml.load(TASKS_YAML),
                related_model='plugins',
                related_id=1,
                graph_type='custom_type'
            )
        )

    def test_execute(self):
        self._test_cmd(
            'execute',
            '--env 1 --type custom_graph --nodes 1 2 3',
            dict(
                env_id=1,
                graph_type='custom_graph',
                nodes=[1, 2, 3],
                dry_run=False
            )
        )

    def test_execute_w_dry_run(self):
        self._test_cmd(
            'execute',
            '--env 1 --type custom_graph --nodes 1 2 3 --dry-run',
            dict(
                env_id=1,
                graph_type='custom_graph',
                nodes=[1, 2, 3],
                dry_run=True
            )
        )

    def test_download(self):
        self._test_cmd(
            'download',
            '--env 1 --all --file existing_graph.yaml --type custom_graph',
            dict(
                env_id=1,
                level='all',
                graph_type='custom_graph'
            )
        )

    def test_list(self):
        with mock.patch('sys.stdout', new=six.moves.cStringIO()) as m_stdout:
            self.m_get_client.reset_mock()
            self.m_client.get_filtered.reset_mock()
            self.m_client.list.return_value = [
                {
                    'name': 'updated-graph-name',
                    'tasks': [{
                        'id': 'test-task2',
                        'type': 'puppet',
                        'task_name': 'test-task2',
                        'version': '2.0.0'
                    }],
                    'relations': [{
                        'model': 'cluster',
                        'model_id': 370,
                        'type': 'custom-graph'
                    }],
                    'id': 1
                }
            ]
            self.exec_command('graph list --env 1')
            self.m_get_client.assert_called_once_with('graph', mock.ANY)
            self.m_client.list.assert_called_once_with(env_id=1)

            self.assertIn('1', m_stdout.getvalue())
            self.assertIn('updated-graph-name', m_stdout.getvalue())
            self.assertIn('custom-graph', m_stdout.getvalue())
            self.assertIn('test-task2', m_stdout.getvalue())
