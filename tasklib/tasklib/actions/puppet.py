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

import logging
import os

from tasklib.actions import action
from tasklib import exceptions
from tasklib import utils

log = logging.getLogger(__name__)


class PuppetAction(action.Action):

    def run(self):
        log.debug('Running puppet task %s with command %s',
                  self.task.name, self.command)
        exit_code, stdout, stderr = utils.execute(self.command)
        log.debug(
            'Task %s with command %s\n returned code %s\n out %s err%s',
            self.task.name, self.command, exit_code, stdout, stderr)
        # 0 - no changes
        # 2 - was some changes but successfull
        # 4 - failures during transaction
        # 6 - changes and failures
        if exit_code not in [0, 2]:
            raise exceptions.Failed()
        return exit_code

    @property
    def manifest(self):
        return (self.task.metadata.get('puppet_manifest') or
                self.config['puppet_manifest'])

    @property
    def puppet_options(self):
        if 'puppet_options' in self.task.metadata:
            return self.task.metadata['puppet_options']
        return self.config['puppet_options']

    @property
    def puppet_modules(self):
        return (self.task.metadata.get('puppet_modules') or
                self.config['puppet_modules'])

    @property
    def command(self):
        cmd = ['puppet', 'apply', '--detailed-exitcodes']
        if self.puppet_modules:
            cmd.append('--modulepath={0}'.format(self.puppet_modules))
        if self.puppet_options:
            cmd.append(self.puppet_options)
        if self.config['debug']:
            cmd.append('--debug --verbose --evaltrace')
        cmd.append(os.path.join(self.task.dir, self.manifest))
        return ' '.join(cmd)
