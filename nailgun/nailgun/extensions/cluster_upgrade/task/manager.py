# -*- coding: utf-8 -*-

#    Copyright 2013 Mirantis, Inc.
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

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun.errors import errors
from nailgun.logger import logger
import nailgun.rpc as rpc
from nailgun.task import manager as task_manager

from . import helpers
from ..objects.adapters import NailgunNodeAdapter
from . import task


class UpgradeEnvironmentTaskManager(task_manager.TaskManager):

    def execute(self):
        if not self.cluster.pending_release_id:
            raise errors.InvalidReleaseId(
                u"Can't update environment '{0}' when "
                u"new release Id is invalid".format(self.cluster.name))

        running_tasks = db().query(models.Task).filter_by(
            cluster_id=self.cluster.id,
            status='running'
        ).filter(
            models.Task.name.in_([
                consts.TASK_NAMES.deploy,
                consts.TASK_NAMES.deployment,
                consts.TASK_NAMES.reset_environment,
                consts.TASK_NAMES.stop_deployment,
                consts.TASK_NAMES.upgrade
            ])
        )
        if running_tasks.first():
            raise errors.TaskAlreadyRunning(
                u"Can't update environment '{0}' when "
                u"other task is running".format(
                    self.cluster.id
                )
            )

        nodes_to_upgrade = helpers.TaskHelper.nodes_to_upgrade(self.cluster)
        logger.debug('Nodes to upgrade: {0}'.format(
            ' '.join([NailgunNodeAdapter.get_node_fqdn(n)
                      for n in nodes_to_upgrade])))
        upgrade_task = models.Task(name=consts.TASK_NAMES.upgrade,
                                   cluster=self.cluster)
        db().add(upgrade_task)
        self.cluster.status = consts.CLUSTER_STATUSES.upgrade
        db().flush()

        deployment_message = self._call_silently(
            upgrade_task,
            task.UpgradeTask,
            nodes_to_upgrade,
            method_name='message')

        db().refresh(upgrade_task)

        for node in nodes_to_upgrade:
            node.status = 'deploying'
            node.progress = 0

        db().commit()
        rpc.cast('naily', deployment_message)

        return upgrade_task
