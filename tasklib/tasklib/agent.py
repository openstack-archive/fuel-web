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

import daemonize

from tasklib import exceptions
from tasklib import task
from tasklib import utils


log = logging.getLogger(__name__)


class TaskAgent(object):

    def __init__(self, task_name, config):
        log.debug('Initializing task agent for task %s', task_name)
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
            self.set_status(utils.STATUS.running.name)
            result = self.task.run()
            self.set_status(utils.STATUS.end.name)
            return result
        except exceptions.NotFound as exc:
            log.warning('Cant find task %s with path %s',
                        self.task.name, self.task.file)
            self.set_status(utils.STATUS.notfound.name)
        except exceptions.Failed as exc:
            log.error('Task %s failed with msg %s', self.task.name, exc.msg)
            self.set_status(utils.STATUS.failed.name)
        except Exception:
            log.exception('Task %s erred', self.task.name)
            self.set_status(utils.STATUS.error.name)
        finally:
            self.clean()

    def __str__(self):
        return 'tasklib agent - {0}'.format(self.task.name)

    def report(self):
        return 'placeholder'

    def status(self):
        if not os.path.exists(self.task.status_file):
            return utils.STATUS.notfound.name
        with open(self.task.status_file) as f:
            return f.read()

    def set_status(self, status):
        with open(self.task.status_file, 'w') as f:
            f.write(status)

    def code(self):
        status = self.status()
        return getattr(utils.STATUS, status).code

    @property
    def pid(self):
        return os.path.join(self.task.pid_dir, 'run.pid')

    def daemon(self):
        log.debug('Daemonizing task %s with pidfile %s',
                  self.task.name, self.pid)
        daemon = daemonize.Daemonize(
            app=str(self), pid=self.pid, action=self.run)
        daemon.start()

    def clean(self):
        if os.path.exists(self.pid):
            os.unlink(self.pid)
