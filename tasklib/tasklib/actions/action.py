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

from tasklib import exceptions


log = logging.getLogger(__name__)


class Action(object):

    def __init__(self, task, config):
        self.task = task
        self.config = config
        log.debug('Init action with task %s', self.task.name)

    def verify(self):
        if 'type' not in self.task.metadata:
            raise exceptions.NotValidMetadata()

    def run(self):
        raise NotImplementedError('Should be implemented by action driver.')
