#    Copyright 2014 Mirantis, Inc.
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
import unittest

from fuelclient.cli import error
from fuelclient import client
from fuelclient.commands import environment


class MyApp():
    """Mock of main cliff application class.
    Is supposed to provide stdout obj.
    """
    def __init__(self, _stdout):
        self.stdout = _stdout


class FakeStdout:

    def __init__(self):
        self.content = []

    def write(self, text):
        self.content.append(text)

    def make_string(self):
        result = ''
        for line in self.content:
            result = result + line
        return result


class BaseTestCommand(unittest.TestCase):
    def _fake_execute_cmd(self, prog_name, cmd, cmd_args):
        cmd_parser = cmd.get_parser(prog_name)
        parsed_args, _values_specs = cmd_parser.parse_known_args(cmd_args)
        cmd.run(parsed_args)

    def _show_one_output_parser(self, string_to_parse):
        parsed = []
        for line in string_to_parse.split('\n'):
            # get rid of row delimiters
            if not line or line.startswith('+'):
                continue

            elems = [elem.strip() for elem in line.split('|') if elem]
            # omit header of output table
            if elems[0] == 'Field':
                continue

            parsed.append(elems)

        return parsed


class TestEnvCreate(BaseTestCommand):
    request_to_mock = 'post_request'
    return_data = {'id': 1, 'name': 'test', 'mode': 'ha',
                   'status': 'new', 'net_provider': 'nova',
                   'release_id': 1, 'changes': [{}]}

    def test_env_creation(self):
        # ouput should contain two fields
        elems_count = 2

        cmd_args = ['test', '1', '--mode', 'ha']

        fake_stdout = FakeStdout()
        cmd = environment.EnvCreate(MyApp(fake_stdout), None)

        with mock.patch.object(client.APIClient, self.request_to_mock,
                               return_value=self.return_data):
            self._fake_execute_cmd('create', cmd, cmd_args)

        parsed_output = self._show_one_output_parser(
            fake_stdout.make_string()
        )

        for elem in parsed_output:
            self.assertEqual(len(elem), elems_count)
            self.assertIn(elem[0], environment.EnvCreate.columns_names)
            self.assertTrue(self.return_data.get(elem[0]))

    def test_env_creation_nst_arguments_check(self):
        cmd_args = ['test', '1', '--net', 'neutron']
        cmd = environment.EnvCreate(MyApp(None), None)
        self.assertRaises(error.ArgumentException, self._fake_execute_cmd,
                          'create', cmd, cmd_args)

    def test_env_create_with_proper_data(self):
        url = 'clusters/'
        data_to_send = {
            'name': 'test',
            'release_id': 1,
            'mode': 'ha_compact',
            'net_provider': 'nova_network',
            'net_segment_type': None,
            'nodes': [],
            'tasks': []
        }

        cmd_args = ['test', '1', '--net', 'nova', '--mode', 'ha']
        fake_stdout = FakeStdout()
        cmd = environment.EnvCreate(MyApp(fake_stdout), None)

        with mock.patch.object(client.APIClient, self.request_to_mock) \
                as mocked:
            self._fake_execute_cmd('create', cmd, cmd_args)
            mocked.assert_called_with(url, data_to_send)
