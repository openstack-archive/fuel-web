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

from tasklib.actions import action
from tasklib import exceptions
from tasklib import utils

log = logging.getLogger(__name__)


class ExecAction(action.Action):

    def verify(self):
        super(ExecAction, self).verify()
        if 'cmd' not in self.task.metadata:
            raise exceptions.NotValidMetadata()

    @property
    def command(self):
        return self.task.metadata['cmd']

    def run(self):
        log.debug('Running task %s with command %s',
                  self.task.name, self.command)
        exit_code, stdout, stderr = utils.execute(self.command)
        log.debug(
            'Task %s with command %s\n returned code %s\n out %s err%s',
            self.task.name, self.command, exit_code, stdout, stderr)
        if exit_code != 0:
            raise exceptions.Failed()
        return exit_code
