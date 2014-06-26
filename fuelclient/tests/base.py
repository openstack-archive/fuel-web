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

try:
    from unittest.case import TestCase
except ImportError:
    # Runing unit-tests in production environment
    from unittest2.case import TestCase

import logging
import os
import shutil
import subprocess
import sys
import tempfile

logging.basicConfig(stream=sys.stderr)
logging.getLogger("CliTest.ExecutionLog").setLevel(logging.DEBUG)


class CliExectutionResult:
    def __init__(self, process_handle):
        self.return_code = process_handle.returncode
        self.stdout = process_handle.stdout.read()
        self.stderr = process_handle.stderr.read()

    @property
    def has_errors(self):
        return bool(len(self.stderr))

    @property
    def is_return_code_zero(self):
        return self.return_code == 0


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
            [" ".join(args + (">/dev/null", "2>&1"))],
            shell=True
        )
        print("Running " + " ".join(args))
        handle.wait()

    def run_cli_command(self, command_line, check_errors=False):
        modified_env = os.environ.copy()
        modified_env["LISTEN_PORT"] = "8003"
        command_args = [" ".join((self.fuel_path, command_line))]
        log = logging.getLogger("CliTest.ExecutionLog")
        process_handle = subprocess.Popen(
            command_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            env=modified_env
        )
        process_handle.wait()
        result = CliExectutionResult(process_handle)
        log.debug("command_args: '%s',stdout: '%s', stderr: '%s'",
                  command_args[0], result.stdout, result.stderr)
        if not check_errors:
            if not result.is_return_code_zero or result.has_errors:
                self.fail()
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
