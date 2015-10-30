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
from nailgun.errors import errors
from nailgun.logger import logger
from nailgun import objects
import nailgun.rpc as rpc
from nailgun.task import manager as task_manager

from . import helpers
from ..objects import adapters
from . import task


class UpgradeEnvironmentTaskManager(task_manager.TaskManager):
    def __init__(self, cluster_id=None):
        if cluster_id:
            self.cluster = adapters.NailgunClusterAdapter.get_by_id(
                cluster_id, lock_for_update=True)

    @staticmethod
    def check_running_tasks(cluster):
        cluster_tasks = objects.TaskCollection.get_by_cluster_id(cluster.id)
        running_tasks = objects.TaskCollection.filter_by_list(
            cluster_tasks,
            'name',
            (consts.TASK_NAMES.deploy,
             consts.TASK_NAMES.deployment,
             consts.TASK_NAMES.reset_environment,
             consts.TASK_NAMES.stop_deployment,
             consts.TASK_NAMES.upgrade)
        )
        running_tasks = objects.TaskCollection.filter_by_list(
            running_tasks,
            'status',
            (consts.TASK_STATUSES.pending,
             consts.TASK_STATUSES.running)
        )
        if running_tasks.exists():
            raise errors.TaskAlreadyRunning(
                u"Can't upgrade environment '{0}' when "
                u"other task is running".format(cluster.id)
            )

    def execute(self):
        if not self.cluster.pending_release_id:
            raise errors.InvalidReleaseId(
                u"Can't upgrade environment '{0}' when "
                u"new release Id is invalid".format(self.cluster.name))

        self.check_running_tasks(self.cluster)

        nodes_to_upgrade = helpers.TaskHelper.nodes_to_upgrade(self.cluster)
        logger.debug('Nodes to upgrade: {0}'.format(
            ' '.join(n.fqdn for n in nodes_to_upgrade)))

        upgrade_task = objects.Task.create({
            'name': consts.TASK_NAMES.upgrade,
            'cluster_id': self.cluster.id,
        })
        self.cluster.update({
            'status': consts.CLUSTER_STATUSES.upgrade,
        })

        deployment_message = self._call_silently(
            upgrade_task,
            task.UpgradeTask,
            nodes_to_upgrade,
            method_name='message')

        db().refresh(upgrade_task)

        for node in nodes_to_upgrade:
            node.status = consts.NODE_STATUSES.deploying
            node.progress = 0

        db().commit()
        rpc.cast('naily', deployment_message)

        return upgrade_task
