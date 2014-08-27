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
import six

try:
    from unittest.case import TestCase
except ImportError:
    # Runing unit-tests in production environment
    from unittest2.case import TestCase

from fuelclient.cli import error
from fuelclient import client
from fuelclient.commands import environment_command


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


class _EnvironmentTestMixin:
    def _fake_execute_cmd(self, cmd, cmd_args, prog_name='fuelclient'):
        cmd_parser = cmd.get_parser(prog_name)
        parsed_args, _values_specs = cmd_parser.parse_known_args(cmd_args)
        cmd.run(parsed_args)

    def _get_elems_from_parsed_output(self, string_to_parse):
        parsed = []
        # get rid of row delimiters
        for line in string_to_parse.split('\n'):
            if not line or line.startswith('+'):
                continue

            elems = [elem.strip() for elem in line.split('|') if elem]
            parsed.append(elems)

        return parsed

    def show_one_output_parser(self, string_to_parse):
        to_check = []
        parsed = self._get_elems_from_parsed_output(string_to_parse)
        # header always will be first element in `parsed`
        # we need to remove it as only table rows are crucial
        to_check.append(dict(parsed[1:]))

        return to_check

    def list_output_parser(self, string_to_parse):
        to_check = []
        parsed = self._get_elems_from_parsed_output(string_to_parse)

        # header always will be the first element in `parsed`
        # we use header data to build make data structure suitable
        # for further analisys
        fields_names, parsed = parsed[0], parsed[1:]
        for parsed_elem in parsed:
            elem_to_check = dict(zip(fields_names, parsed_elem))
            to_check.append(elem_to_check)

        return to_check

    def _eval_output_to_verify(self, name, value):
        caster = {
            ('name', 'mode', 'status', 'net_provider'):
            lambda value: str(value),

            ('release_id',): lambda value: int(value),

            ('changes',): lambda value: eval(value)
        }
        to_return = [cast_func(value) for fields, cast_func in
                     six.iteritems(caster) if name in fields].pop()
        return to_return

    def verify_show_env_command(self, cmd_args, columns_to_compare,
                                command_output_parser, return_value=[{}]):

        with mock.patch.object(client.APIClient, self.request_to_mock,
                               return_value=return_value):
            self._fake_execute_cmd(self.cmd, cmd_args)

        parsed_output = command_output_parser(
            self.fake_stdout.make_string()
        )

        for elem in parsed_output:
            self.assertEqual(
                set(columns_to_compare),
                set(elem.keys())
            )
            self.assertNotIn('not_displayable', elem.keys())

            elem_id = int(elem['id'])
            elem_to_compare = [data for data in self.return_data
                               if data['id'] == elem_id].pop()

            for key, value in six.iteritems(elem):
                if key in ('not_displayable', 'id'):
                    continue

                self.assertEqual(
                    self._eval_output_to_verify(key, value),
                    elem_to_compare[key]
                )

    def check_request_mock_called_with_args(self, cmd_args, *called_args):
        with mock.patch.object(client.APIClient, self.request_to_mock) \
                as mocked:
            self._fake_execute_cmd(self.cmd, cmd_args)

            mocked.assert_called_with(*called_args)


class TestEnvCreate(_EnvironmentTestMixin, TestCase):
    request_to_mock = 'post_request'
    return_data = [{'id': 1, 'name': 'test', 'mode': 'ha',
                    'status': 'new', 'net_provider': 'nova',
                    'release_id': 1, 'changes': [{}],
                    'not_displayable': None}]

    def setUp(self):
        self.fake_stdout = FakeStdout()
        self.cmd = environment_command.EnvCreate(MyApp(self.fake_stdout),
                                                 None)

    def test_env_creation(self):
        cmd_args = ['test', '1', '--mode', 'ha']

        self.verify_show_env_command(
            cmd_args,
            environment_command.EnvCreate.columns_names,
            self.show_one_output_parser,
            self.return_data[0]
        )

    def test_env_creation_nst_arguments_check(self):
        cmd_args = ['test', '1', '--net', 'neutron']
        self.assertRaises(error.ArgumentException, self._fake_execute_cmd,
                          self.cmd, cmd_args)

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

        self.check_request_mock_called_with_args(cmd_args, url, data_to_send)


class TestEnvDelete(_EnvironmentTestMixin, TestCase):
    cmd_args = ['1']
    request_to_mock = 'delete_request'

    def setUp(self):
        self.fake_stdout = FakeStdout()
        self.cmd = environment_command.EnvDelete(MyApp(self.fake_stdout),
                                                 None)

    def test_delete_command(self):
        mustbe_output = "Environment with id 1 was deleted\n"

        with mock.patch.object(client.APIClient, self.request_to_mock):
            self._fake_execute_cmd(self.cmd, self.cmd_args)

        self.assertEqual(self.fake_stdout.make_string(), mustbe_output)

    def test_delete_supply_proper_id(self):
        url = 'clusters/1/'
        self.check_request_mock_called_with_args(self.cmd_args, url)


class TestEnvShow(_EnvironmentTestMixin, TestCase):
    cmd_args = ['1']
    request_to_mock = 'get_request'
    return_data = [{'id': 1, 'name': 'test', 'mode': 'ha',
                    'status': 'new', 'net_provider': 'nova',
                    'release_id': 1, 'changes': [{}],
                    'not_displayable': None}]

    def setUp(self):
        self.fake_stdout = FakeStdout()
        self.cmd = environment_command.EnvShow(MyApp(self.fake_stdout), None)

    def test_show_env(self):
        self.verify_show_env_command(
            self.cmd_args,
            environment_command.EnvShow.columns_names,
            self.show_one_output_parser,
            self.return_data[0]
        )

    def test_get_http_request_with_proper_args(self):
        url = 'clusters/1/'
        self.check_request_mock_called_with_args(self.cmd_args, url)


class TestEnvList(_EnvironmentTestMixin, TestCase):
    request_to_mock = 'get_request'
    return_data = [
        {'id': 1, 'name': 'test', 'mode': 'ha',
         'status': 'new', 'net_provider': 'nova',
         'release_id': 1, 'changes': [{}],
         'not_displayable': None},

        {'id': 2, 'name': 'test_two', 'mode': 'ha',
         'status': 'error', 'net_provider': 'neutron',
         'release_id': 2, 'changes': [{}],
         'not_displayable': None},

        {'id': 3, 'name': 'test', 'mode': 'multinode',
         'status': 'operational', 'net_provider': 'nova',
         'release_id': 1, 'changes': [{}],
         'not_displayable': None}
    ]

    def setUp(self):
        self.fake_stdout = FakeStdout()
        self.cmd = environment_command.EnvList(MyApp(self.fake_stdout), None)

    def test_env_list(self):
        self.verify_show_env_command(
            [],
            environment_command.EnvList.columns_names,
            self.list_output_parser,
            self.return_data
        )


class TestEnvUpdate(_EnvironmentTestMixin, TestCase):
    request_to_mock = 'put_request'
    return_data = [{'id': 1, 'name': 'test', 'mode': 'multinode',
                    'status': 'new', 'net_provider': 'nova',
                    'release_id': 1, 'changes': [{}],
                    'not_displayable': None}]

    def setUp(self):
        self.fake_stdout = FakeStdout()
        self.cmd = environment_command.EnvUpdate(MyApp(self.fake_stdout),
                                                 None)

    def test_env_update_successfully(self):
        cmd_args = ['1', 'test', 'multinode']
        self.verify_show_env_command(
            cmd_args,
            environment_command.EnvUpdate.columns_names,
            self.show_one_output_parser,
            self.return_data[0]
        )

    def test_update_http_request_with_proper_args(self):
        cmd_args = ['1', 'test', 'ha']
        url = 'clusters/1/'
        data_to_send = {
            'mode': 'ha_compact',
            'name': 'test'
        }
        self.check_request_mock_called_with_args(cmd_args, url, data_to_send)


class TestEnvUpgrade(_EnvironmentTestMixin, TestCase):
    cmd_args = ['1', '2']
    request_to_mock = 'put_request'
    return_value = {'id': 1}

    def setUp(self):
        self.fake_stdout = FakeStdout()
        self.cmd = environment_command.EnvUpgrade(MyApp(self.fake_stdout),
                                                  None)

    def test_environment_updagrade_successfully(self):
        mustbe_output = ("Update process for environment has been started. "
                         "Update task id is 1\n")
        with mock.patch.object(client.APIClient, self.request_to_mock,
                               return_value=self.return_value):
            self._fake_execute_cmd(self.cmd, self.cmd_args)

        self.assertEqual(self.fake_stdout.make_string(), mustbe_output)

    def test_put_http_request_with_proper_args(self):
        url = 'clusters/1/update/'
        data_to_send = {}
        self.check_request_mock_called_with_args(self.cmd_args, url,
                                                 data_to_send)
