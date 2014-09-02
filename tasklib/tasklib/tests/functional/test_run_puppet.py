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

from tasklib.tests import base


class TestFunctionalExecTasks(base.BaseFunctionalTest):
    """Each test will follow next pattern:
    1. Run test with provided name - taskcmd -c conf.yaml run test/test
    2. check status of task
    """

    def test_puppet_file(self):
        test_file = '/tmp/tasklibtest'
        if os.path.exists(test_file):
            os.unlink(test_file)
        exit_code, out, err = self.execute(['run', 'puppet/file'])
        self.assertEqual(exit_code, 0)

    def test_puppet_invalid(self):
        exit_code, out, err = self.execute(['run', 'puppet/invalid'])
        self.assertEqual(exit_code, 2)

    def test_puppet_cmd(self):
        exit_code, out, err = self.execute(['run', 'puppet/cmd'])
        self.assertEqual(exit_code, 0)
