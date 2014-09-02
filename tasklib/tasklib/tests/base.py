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
import time

import unittest

from tasklib import utils
from tasklib.utils import STATUS


class BaseUnitTest(unittest.TestCase):
    """Tasklib base unittest."""


class BaseFunctionalTest(BaseUnitTest):

    def setUp(self):
        self.dir_path = os.path.dirname(os.path.realpath(__file__))
        self.conf_path = os.path.join(self.dir_path, 'functional', 'conf.yaml')
        self.base_command = ['taskcmd', '-c', self.conf_path]

    def check_puppet_installed(self):
        exit_code, out, err = utils.execute('which puppet')
        if exit_code == 1:
            self.skipTest('Puppet is not installed')

    def execute(self, add_command):
        command = self.base_command + add_command
        cmd = ' '.join(command)
        return utils.execute(cmd)

    def wait_ready(self, cmd, timeout):
        started = time.time()
        while time.time() - started < timeout:
            exit_code, out, err = self.execute(cmd)
            if out.strip('\n') != STATUS.running.name:
                return exit_code, out, err
        self.fail('Command {0} failed to finish with timeout {1}'.format(
                  cmd, timeout))
