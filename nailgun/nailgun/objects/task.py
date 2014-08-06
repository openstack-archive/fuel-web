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

import copy

from nailgun.objects.serializers.task import TaskSerializer

from nailgun.db import db
from nailgun.db.sqlalchemy import models

from nailgun import consts

from nailgun.errors import errors

from nailgun.logger import logger

from nailgun.objects import Cluster
from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject

from nailgun.task.helpers import TaskHelper


class Task(NailgunObject):

    model = models.Task
    serializer = TaskSerializer

    schema = {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "title": "Task",
        "description": "Serialized Task object",
        "type": "object",
        "properties": {
            "id": {"type": "number"},
            "cluster_id": {"type": "number"},
            "parent_id": {"type": "number"},
            "name": {
                "type": "string",
                "enum": list(consts.TASK_NAMES)
            },
            "message": {"type": "string"},
            "status": {
                "type": "string",
                "enum": list(consts.TASK_STATUSES)
            },
            "progress": {"type": "number"},
            "weight": {"type": "number"},
            "cache": {"type": "object"},
            "result": {"type": "object"}
        }
    }

    @classmethod
    def create_subtask(cls, instance, name):
        if name not in consts.TASK_NAMES:
            raise errors.InvalidData(
                "Invalid subtask name"
            )

        return cls.create({
            "name": name,
            "cluster_id": instance.cluster_id,
            "parent_id": instance.id
        })

    @classmethod
    def get_by_uuid(cls, uuid, fail_if_not_found=False, lock_for_update=False):
        # maybe consider using uuid as pk?
        q = db().query(cls.model).filter_by(uuid=uuid)
        if lock_for_update:
            q = q.order_by('id')
            q = q.with_lockmode('update')
        res = q.first()

        if not res and fail_if_not_found:
            raise errors.ObjectNotFound(
                "Task with UUID={0} is not found in DB".format(uuid)
            )
        return res

    @classmethod
    def update_verify_networks(cls, instance, status,
                               progress, msg, result):
        #TODO(dshulyak) move network tests into ostf
        previous_status = instance.status

        statuses = [sub.status for sub in instance.subtasks]
        messages = [sub.message for sub in instance.subtasks]
        messages.append(msg)
        statuses.append(status)
        if any(st == 'error' for st in statuses):
            instance.status = 'error'
        else:
            instance.status = status or instance.status
        instance.progress = progress or instance.progress
        instance.result = result or instance.result
        # join messages if not None or ""
        instance.message = '\n'.join([m for m in messages if m])
        if previous_status != instance.status and instance.cluster_id:
            logger.debug("Updating cluster status: "
                         "cluster_id: %s status: %s",
                         instance.cluster_id, status)
            cls._update_cluster_data(instance)

    @classmethod
    def _update_parent_instance(cls, instance):
        subtasks = instance.subtasks
        if len(subtasks):
            data = dict()

            if all(map(lambda s: s.status == 'ready', subtasks)):

                data['status'] = 'ready'
                data['progress'] = 100
                data['message'] = u'\n'.join(map(
                    lambda s: s.message, filter(
                        lambda s: s.message is not None, subtasks)))

                cls.update(instance, data)

            elif any(map(lambda s: s.status in ('error',), subtasks)):
                for subtask in subtasks:
                    if not subtask.status in ('error', 'ready'):
                        subtask.status = 'error'
                        subtask.progress = 100
                        subtask.message = 'Task aborted'

                data['status'] = 'error'
                data['progress'] = 100
                data['message'] = u'\n'.join(list(set(map(
                    lambda s: (s.message or ""), filter(
                        lambda s: (
                            s.status == 'error' and not
                            # TODO: make this check less ugly
                            s.message == 'Task aborted'
                        ), subtasks)))))

                cls.update(instance, data)
            else:
                subtasks_with_progress = filter(
                    lambda s: s.progress is not None,
                    subtasks
                )
                if subtasks_with_progress:
                    instance.progress = \
                        TaskHelper.calculate_parent_task_progress(
                            subtasks_with_progress
                        )
                else:
                    instance.progress = 0

    @classmethod
    def __update_nodes_to_error(cls, q_nodes_to_error, error_type):
        if q_nodes_to_error.count():
            logger.debug(
                u'Updating nodes to error with error_type "{0}": {1}'
                .format(error_type, [n.full_name for n in q_nodes_to_error]))

            for n in q_nodes_to_error:
                n.status = 'error'
                n.progress = 0
                n.error_type = error_type

    @classmethod
    def __update_cluster_status(cls, cluster, status):
        logger.debug(
            "Updating cluster (%s) status: from %s to %s",
            cluster.full_name, cluster.status, status)
        Cluster.update(cluster, data={'status': status})

    @classmethod
    def _update_cluster_data(cls, instance):
        cluster = instance.cluster

        if instance.name == 'deploy':
            if instance.status == 'ready':
                # If for some reasosns orchestrator
                # didn't send ready status for node
                # we should set it explicitly
                for n in cluster.nodes:
                    if n.status == 'deploying':
                        n.status = 'ready'
                        n.progress = 100

                cls.__update_cluster_status(cluster, 'operational')

                Cluster.clear_pending_changes(cluster)

            elif instance.status == 'error' and \
                    not TaskHelper.before_deployment_error(instance):
                # We don't want to set cluster status to
                # error because we don't want to lock
                # settings if cluster wasn't delpoyed

                cls.__update_cluster_status(cluster, 'error')

        elif instance.name == 'deployment' and instance.status == 'error':
            cls.__update_cluster_status(cluster, 'error')

            q_nodes_to_error = \
                TaskHelper.get_nodes_to_deployment_error(cluster)

            cls.__update_nodes_to_error(q_nodes_to_error,
                                        error_type='deploy')

        elif instance.name == 'provision' and instance.status == 'error':
            cls.__update_cluster_status(cluster, 'error')

            q_nodes_to_error = \
                TaskHelper.get_nodes_to_provisioning_error(cluster)

            cls.__update_nodes_to_error(q_nodes_to_error,
                                        error_type='provision')

        elif instance.name == 'stop_deployment':
            if instance.status == 'error':
                cls.__update_cluster_status(cluster, 'error')
            else:
                cls.__update_cluster_status(cluster, 'stopped')

        elif instance.name == consts.TASK_NAMES.update:
            if instance.status == consts.TASK_STATUSES.error:
                cls.__update_cluster_status(
                    cluster,
                    consts.CLUSTER_STATUSES.update_error
                )

                q_nodes_to_error = \
                    TaskHelper.get_nodes_to_deployment_error(cluster)
                cls.__update_nodes_to_error(
                    q_nodes_to_error, error_type=consts.NODE_ERRORS.deploy)

            elif instance.status == consts.TASK_STATUSES.ready:
                cls.__update_cluster_status(
                    cluster,
                    consts.CLUSTER_STATUSES.operational
                )
                cluster.release_id = cluster.pending_release_id
                cluster.pending_release_id = None

    @classmethod
    def _clean_data(cls, data):
        result = copy.copy(data)
        if result.get('status') not in consts.TASK_STATUSES:
            result.pop('status', None)
        return result

    @classmethod
    def update(cls, instance, data):
        logger.debug("Updating task: %s", instance.uuid)
        clean_data = cls._clean_data(data)
        super(Task, cls).update(instance, clean_data)
        db().flush()

        if instance.cluster_id:
            logger.debug("Updating cluster status: %s "
                         "cluster_id: %s status: %s",
                         instance.uuid, instance.cluster_id,
                         data.get('status'))
            cls._update_cluster_data(instance)

        if instance.parent:
            logger.debug("Updating parent task: %s.", instance.parent.uuid)
            cls._update_parent_instance(instance.parent)


class TaskCollection(NailgunCollection):

    single = Task

    @classmethod
    def get_by_cluster_id(cls, cluster_id):
        if cluster_id == '':
            return cls.filter_by(None, cluster_id=None)
        return cls.filter_by(None, cluster_id=cluster_id)

    @classmethod
    def lock_cluster_tasks(cls, cluster_id, names=None):
        query = cls.get_by_cluster_id(cluster_id)
        if isinstance(names, (list, tuple)):
            query = cls.filter_by_list(query, 'name', names)
        query = cls.order_by(query, 'id')
        query = cls.lock_for_update(query)
        return query.all()

    @classmethod
    def delete_by_names(cls, cluster_id, names):
        db().query(cls.single.model).filter_by(
            cluster_id=cluster_id,
        ).filter(
            cls.single.model.name.in_(names)
        ).delete(
            synchronize_session='fetch'
        )
