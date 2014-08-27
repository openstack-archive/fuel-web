#    Copyright 2013-2014 Mirantis, Inc.
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

import logging
import mock
import os
import shutil
import six
import subprocess
import sys
import tempfile


from fuelclient import client

from tests import utils

try:
    from unittest.case import TestCase
except ImportError:
    # Runing unit-tests in production environment
    from unittest2.case import TestCase

logging.basicConfig(stream=sys.stderr)
log = logging.getLogger("CliTest.ExecutionLog")
log.setLevel(logging.DEBUG)


# TODO(aroma): remove it after complete move to cliff
class CliExectutionResult:
    def __init__(self, process_handle, out, err):
        self.return_code = process_handle.returncode
        self.stdout = out
        self.stderr = err

    @property
    def has_errors(self):
        return bool(len(self.stderr))

    @property
    def is_return_code_zero(self):
        return self.return_code == 0


# TODO(aroma): remove it after complete move to cliff
class BaseTestCase(TestCase):
    root_path = os.path.abspath(
        os.path.join(
            os.curdir,
            os.path.pardir
        )
    )
    manage_path = os.path.join(
        root_path,
        "nailgun/manage.py"
    )
    fuel_path = os.path.join(
        root_path,
        "fuelclient/fuel"
    )

    def setUp(self):
        self.reload_nailgun_server()
        self.temp_directory = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_directory)

    def upload_command(self, cmd):
        return "{0} --upload --dir {1}".format(cmd, self.temp_directory)

    def download_command(self, cmd):
        return "{0} --download --dir {1}".format(cmd, self.temp_directory)

    @classmethod
    def reload_nailgun_server(cls):
        for action in ("dropdb", "syncdb", "loaddefault"):
            cls.run_command(cls.manage_path, action)

    @classmethod
    def load_data_to_nailgun_server(cls):
        cls.run_command(cls.manage_path, "loaddata {0}".format(
            os.path.join(
                cls.root_path,
                "nailgun/nailgun/fixtures/sample_environment.json"
            )
        ))

    @staticmethod
    def run_command(*args):
        handle = subprocess.Popen(
            [" ".join(args)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True
        )
        log.debug("Running " + " ".join(args))
        out, err = handle.communicate()
        log.debug("Finished command with {0} - {1}".format(out, err))

    def run_cli_command(self, command_line, check_errors=False):
        modified_env = os.environ.copy()
        command_args = [" ".join((self.fuel_path, command_line))]
        process_handle = subprocess.Popen(
            command_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            env=modified_env
        )
        out, err = process_handle.communicate()
        result = CliExectutionResult(process_handle, out, err)
        log.debug("command_args: '%s',stdout: '%s', stderr: '%s'",
                  command_args[0], out, err)
        if not check_errors:
            if not result.is_return_code_zero or result.has_errors:
                self.fail(err)
        return result

    def run_cli_commands(self, command_lines, **kwargs):
        for command in command_lines:
            self.run_cli_command(command, **kwargs)

    def check_if_required(self, command):
        call = self.run_cli_command(command, check_errors=True)
        #should not work without env id
        self.assertIn("required", call.stderr)

    def check_for_stdout(self, command, msg):
        call = self.run_cli_command(command)
        self.assertEqual(call.stdout, msg)

    def check_all_in_msg(self, command, substrings, **kwargs):
        output = self.run_cli_command(command, **kwargs)
        for substring in substrings:
            self.assertIn(substring, output.stdout)

    def check_for_rows_in_table(self, command):
        output = self.run_cli_command(command)
        message = output.stdout.split("\n")
        #no env
        self.assertEqual(message[2], '')

    def check_number_of_rows_in_table(self, command, number_of_rows):
        output = self.run_cli_command(command)
        self.assertEqual(len(output.stdout.split("\n")), number_of_rows + 3)


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


class BaseTestCommand(TestCase):

    def setUp(self):
        self.fake_stdout = FakeStdout()
        self.cmd = self.command_class(MyApp(self.fake_stdout), None)

    def _fake_execute_cmd(self, cmd, cmd_args, prog_name='fuelclient'):
        cmd_parser = cmd.get_parser(prog_name)
        parsed_args, _values_specs = cmd_parser.parse_known_args(cmd_args)
        cmd.run(parsed_args)

    def verify_show_command(self, cmd_args, columns_to_compare,
                            command_output_parser=utils.list_output_parser,
                            return_value=[{}]):

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
                    utils.eval_output_to_verify(key, value),
                    elem_to_compare[key]
                )

    def check_request_mock_called_with_args(self, cmd_args, return_value,
                                            *called_args):
        with mock.patch.object(client.APIClient, self.request_to_mock,
                               return_value=return_value) \
                as mocked:
            self._fake_execute_cmd(self.cmd, cmd_args)

            mocked.assert_called_with(*called_args)
