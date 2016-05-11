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
