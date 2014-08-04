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

from fuelclient import client
from fuelclient.commands import environment


class MockApp():
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
    def _fake_execute_cmd(self, prog_name, cmd, cmd_args,
                          httpclient_method_name=None, return_data={}):

        cmd_parser = cmd.get_parser(prog_name)
        parsed_args, _values_specs = cmd_parser.parse_known_args(cmd_args)

        with mock.patch.object(client.APIClient, httpclient_method_name,
                               return_value=return_data):
            cmd.run(parsed_args)


class TestEnvCreate(BaseTestCommand):
    def test_env_creation(self):
        # ouput should contain two fields
        elems_count = 2

        cmd_args = ['test', '1', '--mode', 'ha']
        return_data = {'id': 1, 'name': 'test', 'mode': 'ha',
                       'status': 'new', 'net_provider': 'nova',
                       'release_id': 1, 'changes': [{}]}

        fake_stdout = FakeStdout()
        cmd = environment.EnvCreate(MockApp(fake_stdout), None)

        self._fake_execute_cmd('create', cmd, cmd_args, 'post_request',
                               return_data)

        for line in fake_stdout.make_string().split('\n'):
            if not line or line.startswith('+'):
                continue

            elems = [elem.strip() for elem in line.split('|') if elem]
            # omit header of output table
            if elems[0] == 'Field':
                continue

            self.assertEqual(len(elems), elems_count)
            self.assertIn(elems[0], environment.EnvCreate.columns_names)
            self.assertTrue(return_data.get(elems[0]))
