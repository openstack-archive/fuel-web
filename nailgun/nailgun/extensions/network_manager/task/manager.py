#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy.models import Task
from nailgun.logger import logger
from nailgun.task.manager import TaskManager

from . import task as tasks


class UpdateDnsmasqTaskManager(TaskManager):

    def execute(self, **kwargs):
        logger.info("Starting update_dnsmasq task")
        self.check_running_task(consts.TASK_NAMES.update_dnsmasq)

        task = Task(name=consts.TASK_NAMES.update_dnsmasq)
        db().add(task)
        db().commit()
        self._call_silently(
            task,
            tasks.UpdateDnsmasqTask
        )
        return task
