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

    def __init__(self, task_name, config):
        self.config = config
        task_directory = task_name.replace('::', '/')
        task_path = os.path.join(config['library_dir'], task_directory)
        self.task = task.Task(task_path)

    def run(self):
        return self.task.run()

    def __str__(self):
        return 'task agent - {0}'.format(self.task.name)

    def report(self):
        return 'XML REPORT'

    def status(self):
        return 'status'

    @property
    def pid(self):
        pid_name = '{0}.pid'.format(self.task.name)
        return os.path.join(self.config['pid_dir'], pid_name)

    def daemon(self):
        daemon = daemonize.Daemonize(
            app=str(self), pid=self.pid, action=self.run)
        daemon.start()
