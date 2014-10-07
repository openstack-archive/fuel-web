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

from tasklib.tests import base
from tasklib.utils import STATUS


class TestDaemon(base.BaseFunctionalTest):

    def test_exec_long_task(self):
        exit_code, out, err = self.execute(['daemon', 'exec/long'])
        self.assertEqual(exit_code, 0)
        exit_code, out, err = self.wait_ready(['status', 'exec/long'], 2)
        self.assertEqual(exit_code, 0)
        self.assertEqual(out.strip('\n'), STATUS.end.name)

    def test_puppet_simple_daemon(self):
        self.check_puppet_installed()
        exit_code, out, err = self.execute(['daemon', 'puppet/sleep'])
        self.assertEqual(exit_code, 0)
        exit_code, out, err = self.wait_ready(['status', 'puppet/sleep'], 10)
        self.assertEqual(exit_code, 0)
        self.assertEqual(out.strip('\n'), STATUS.end.name)
