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

import yaml

from tasklib.actions import puppet
from tasklib.actions import exec_action

# use stevedore here
type_mapping = {'exec': exec_action.ExecAction,
                'puppet': puppet.PuppetAction}


class Task(object):
    """Unit of execution. Contains pre/post/run subtasks"""

    def __init__(self, task_name, config):
        self.config = config
        self.name = task_name
        self.dir = os.path.join(
            config['library_dir'], task_name.replace('::', '/'))
        self.file = os.path.join(self.dir, config['task_file'])
        self._metadata = {}

    @property
    def pid_dir(self):
        return os.path.join(self.config['pid_dir'], self.name)

    @property
    def report_dir(self):
        return os.path.join(self.config['report_dir'], self.name)

    @property
    def status_file(self):
        return os.path.join(self.report_dir, self.config['status_file'])

    @property
    def metadata(self):
        if not os.path.exists(self.file):
            return self._metadata
        if self._metadata:
            return self._metadata
        with open(self.file) as f:
            self._metadata = yaml.load(f.read())
        return self._metadata

    @classmethod
    def task_from_dir(cls, task_dir, config):
        path = task_dir.replace(config['library_dir'], '').split('/')
        task_name = '::'.join((p for p in path if p))
        return cls(task_name, config)

    def __repr__(self):
        return "{0:10} | {1:15}".format(self.name, self.dir)

    def run(self):
        """Will be used to run a task."""
        action = type_mapping.get(self.metadata.get('type'))
        if action:
            return action(self, self.config).run()
