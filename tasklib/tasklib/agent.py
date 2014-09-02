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

import daemonize
import yaml

from tasklib import task


class TaskAgent(object):

    def __init__(self, task_name, config, daemonize=True):
        self.config = config
        task_directory = task_name.replace('::', '/')
        self.task_path = os.path.join(config['library_dir'], task_directory)
        self.daemonize = daemonize
        self.task = task.Task(self.task_path)

    def run(self):
        pass

    def __str__(self):
        return 'task agent - {0}'.format(self.task.name)

    @property
    def pid(self):
        return os.path.join(self.config['pid_dir'], self.task.name)

    def daemon(self):
        daemon = daemonize.Daemonize(
            app=str(self), pid=self.task.pid, action=self.run)
        daemon.start()
