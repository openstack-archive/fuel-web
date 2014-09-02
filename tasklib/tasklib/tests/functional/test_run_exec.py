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

import os
import unittest

from tasklib import utils


class TestFunctionalExecTasks(unittest.TestCase):
    """Each test will follow next pattern:
    1. Run test with provided name - taskcmd -c conf.yaml run test/test
    2. check status of task
    """

    def setUp(self):
        self.dir_path = os.path.dirname(os.path.realpath(__file__))
        self.conf_path = os.path.join(self.dir_path, 'conf.yaml')
        self.base_command = ['taskcmd', '-c', self.conf_path]

    def execute(self, add_command):
        command = self.base_command + add_command
        cmd = ' '.join(command)
        return utils.execute(cmd)

    def test_simple_run(self):
        exit_code, out, err = self.execute(['run', 'exec/simple'])
        self.assertEqual(exit_code, 0)
        exit_code, out, err = self.execute(['status', 'exec/simple'])
        self.assertEqual(out.strip('\n'), 'end')
        self.assertEqual(exit_code, 0)

    def test_failed_run(self):
        exit_code, out, err = self.execute(['run', 'exec/fail'])
        self.assertEqual(exit_code, 2)
        exit_code, out, err = self.execute(['status', 'exec/fail'])
        self.assertEqual(out.strip('\n'), 'failed')
        self.assertEqual(exit_code, 2)

    def test_error(self):
        exit_code, out, err = self.execute(['run', 'exec/error'])
        self.assertEqual(exit_code, 3)
        exit_code, out, err = self.execute(['status', 'exec/error'])
        self.assertEqual(out.strip('\n'), 'error')
        self.assertEqual(exit_code, 3)

    def test_notfound(self):
        exit_code, out, err = self.execute(['run', 'exec/notfound'])
        self.assertEqual(exit_code, 4)
        exit_code, out, err = self.execute(['status', 'exec/notfound'])
        self.assertEqual(out.strip('\n'), 'notfound')
        self.assertEqual(exit_code, 4)
