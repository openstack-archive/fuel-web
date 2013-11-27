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

try:
    from unittest.case import TestCase
except ImportError:
    # Runing unit-tests in production environment
    from unittest2.case import TestCase

import logging
import os
import subprocess
import sys

logging.basicConfig(stream=sys.stderr)
logging.getLogger("SomeTest.testSomething").setLevel(logging.DEBUG)


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

    @classmethod
    def setUp(cls):
        cls.reload_nailgun_server()

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

    def run_cli_command(self, command_line=None, with_erros=False):
        modified_env = os.environ.copy()
        modified_env["LISTEN_PORT"] = "8003"
        command_args = [" ".join((self.fuel_path, command_line))]
        log = logging.getLogger("SomeTest.testSomething")
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
        if not with_erros:
            if not result.is_return_code_zero or result.has_errors:
                self.fail()
        return result

    def check_if_required(self, command):
        call = self.run_cli_command(command_line=command, with_erros=True)
        #should not work without env id
        self.assertIn("required", call.stderr)

    def check_for_stdout(self, command, msg):
        call = self.run_cli_command(command_line=command)
        self.assertEqual(call.stdout, msg)

    def check_all_in_msg(self, command, substrs):
        output = self.run_cli_command(command_line=command)
        for substr in substrs:
            self.assertIn(substr, output.stdout)

    def check_for_rows_in_table(self, command):
        output = self.run_cli_command(command_line=command)
        message = output.stdout.split("\n")
        #no env
        self.assertEqual(message[2], '')
