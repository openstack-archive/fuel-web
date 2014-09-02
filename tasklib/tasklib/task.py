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


class Task(object):
    """Unit of execution. Contains pre/post/run subtasks"""

    def __init__(self, task_dir, config):
        self.config = config
        self.task_dir = task_dir
        self.task_file = os.path.join(task_dir, config['task_file'])
        self._metadata = None

    @property
    def metadata(self):
        if self._metadata:
            return self._metadata
        with open(self.task_file) as f:
            self._metadata = yaml.load(f.read())
        return self._metadata

    @property
    def name(self):
        path = self.task_dir.replace(self.config['library_dir'], '').split('/')
        return '::'.join((p for p in path if p))

    def __repr__(self):
        return "{0:10} | {1:15}".format(self.name, self.task_dir)

    def run(self):
        pass
