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

import yaml

from tasklib.actions import exec_action
from tasklib.actions import puppet
from tasklib import exceptions

# use stevedore here
type_mapping = {'exec': exec_action.ExecAction,
                'puppet': puppet.PuppetAction}

log = logging.getLogger(__name__)


class Task(object):
    """Unit of execution. Contains pre/post/run subtasks."""

    def __init__(self, task_name, config):
        self.config = config
        self.name = task_name
        self.dir = os.path.abspath(
            os.path.join(config['library_dir'], self.name))
        self.file = os.path.abspath(
            os.path.join(self.dir, config['task_file']))
        self.pid_dir = os.path.abspath(
            os.path.join(self.config['pid_dir'], self.name))
        self.report_dir = os.path.abspath(
            os.path.join(self.config['report_dir'], self.name))
        self.status_file = os.path.abspath(os.path.join(
            self.report_dir, self.config['status_file']))
        self._metadata = {}
        log.debug('Init task %s with task file %s', self.name, self.file)

    def verify(self):
        if not os.path.exists(self.file):
            raise exceptions.NotFound()

    @property
    def metadata(self):
        if self._metadata:
            return self._metadata
        with open(self.file) as f:
            self._metadata = yaml.load(f.read())
        return self._metadata

    @classmethod
    def task_from_dir(cls, task_dir, config):
        path = task_dir.replace(config['library_dir'], '').split('/')
        task_name = '/'.join((p for p in path if p))
        return cls(task_name, config)

    def __repr__(self):
        return "{0:10} | {1:15}".format(self.name, self.dir)

    def run(self):
        """Will be used to run a task."""
        self.verify()
        action_class = type_mapping.get(self.metadata.get('type'))
        if action_class is None:
            raise exceptions.NotValidMetadata()
        action = action_class(self, self.config)
        action.verify()
        return action.run()
