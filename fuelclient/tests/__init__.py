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

import mock
import six

from fuelclient import client

try:
    from unittest.case import TestCase
except ImportError:
    # Runing unit-tests in production environment
    from unittest2.case import TestCase


class BaseTestCommand(TestCase):
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

    def check_request_mock_called_with_args(self, cmd_args, return_value,
                                            *called_args):
        with mock.patch.object(client.APIClient, self.request_to_mock,
                               return_value=return_value) \
                as mocked:
            self._fake_execute_cmd(self.cmd, cmd_args)

            mocked.assert_called_with(*called_args)
