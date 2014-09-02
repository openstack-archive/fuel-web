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

from tasklib import task
from tasklib import exceptions
from tasklib import utils


class TaskAgent(object):

    def __init__(self, task_name, config):
        self.config = config
        self.task = task.Task(task_name, self.config)
        self.init_directories()

    def init_directories(self):
        utils.ensure_dir_created(self.config['pid_dir'])
        utils.ensure_dir_created(self.config['report_dir'])
        utils.ensure_dir_created(self.task.pid_dir)
        utils.ensure_dir_created(self.task.report_dir)

    def run(self):
        try:
            self.set_status('running')
            result = self.task.run()
            self.set_status('end')
            return result
        except exceptions.NotFound:
            self.set_status('notfound')
        except exceptions.Failed:
            self.set_status('failed')
        except Exception:
            self.set_status('error')
        finally:
            self.clean()

    def __str__(self):
        return 'tasklib agent - {0}'.format(self.task.name)

    def report(self):
        return 'placeholder'

    def status(self):
        with open(self.task.status_file) as f:
            return f.read()

    def set_status(self, status):
        with open(self.task.status_file, 'w') as f:
            f.write(status)

    @property
    def pid(self):
        return os.path.join(self.task.pid_dir, 'run.pid')

    def daemon(self):
        daemon = daemonize.Daemonize(
            app=str(self), pid=self.pid, action=self.run)
        daemon.start()

    def clean(self):
        if os.path.exists(self.pid):
            os.unlink(self.pid)
