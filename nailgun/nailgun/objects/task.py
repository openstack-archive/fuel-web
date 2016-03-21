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
from datetime import datetime

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

    @classmethod
    def get_by_uid(cls, uid, fail_if_not_found=False, lock_for_update=False):
        return cls.get_by_uid_excluding_deleted(uid, fail_if_not_found=False,
                                                lock_for_update=False)

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
    def get_by_uid_excluding_deleted(cls, uid, fail_if_not_found=False,
                                     lock_for_update=False):
        q = db().query(cls.model).filter_by(id=uid).filter_by(deleted_at=None)
        if lock_for_update:
            q = q.order_by('id')
            q = q.with_lockmode('update')
        res = q.first()

        if not res and fail_if_not_found:
            raise errors.ObjectNotFound(
                "Task with ID='{0}' is not found in DB".format(uid)
            )
        return res

    @classmethod
    def update_verify_networks(cls, instance, status,
                               progress, msg, result):
        # TODO(dshulyak) move network tests into ostf
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

            if all(map(lambda s: s.status == consts.TASK_STATUSES.ready,
                       subtasks)):

                data['status'] = consts.TASK_STATUSES.ready
                data['progress'] = 100
                data['message'] = u'\n'.join(map(
                    lambda s: s.message, filter(
                        lambda s: s.message is not None, subtasks)))

                cls.update(instance, data)
                TaskHelper.update_action_log(instance)

            elif any(map(lambda s: s.status == consts.TASK_STATUSES.error,
                         subtasks)):
                for subtask in subtasks:
                    if subtask.status not in (consts.TASK_STATUSES.error,
                                              consts.TASK_STATUSES.ready):
                        subtask.status = consts.TASK_STATUSES.error
                        subtask.progress = 100
                        subtask.message = "Task aborted"

                data['status'] = consts.TASK_STATUSES.error
                data['progress'] = 100
                data['message'] = u'\n'.join(list(set(map(
                    lambda s: (s.message or ""), filter(
                        lambda s: (
                            s.status == consts.TASK_STATUSES.error and not
                            # TODO(aroma): make this check less ugly
                            s.message == "Task aborted"
                        ), subtasks)))))

                cls.update(instance, data)
                TaskHelper.update_action_log(instance)

            elif instance.status == consts.TASK_STATUSES.pending and any(
                    map(lambda s: s.status in (consts.TASK_STATUSES.running,
                                               consts.TASK_STATUSES.ready),
                        subtasks)):
                instance.status = consts.TASK_STATUSES.running

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
    def __update_cluster_status(cls, cluster, status, expected_node_status):
        logger.debug(
            "Updating cluster (%s) status: from %s to %s",
            cluster.full_name, cluster.status, status)

        if expected_node_status is not None:
            remaining = Cluster.get_nodes_count_unmet_status(
                cluster, expected_node_status
            )
            if remaining > 0:
                logger.debug("Detect that cluster '%s' is partially deployed.",
                             cluster.id)
                status = consts.CLUSTER_STATUSES.partially_deployed

        # FIXME(aroma): remove updating of 'deployed_before'
        # when stop action is reworked. 'deployed_before'
        # flag identifies whether stop action is allowed for the
        # cluster. Please, refer to [1] for more details.
        # [1]: https://bugs.launchpad.net/fuel/+bug/1529691
        if status == consts.CLUSTER_STATUSES.operational:
            Cluster.set_deployed_before_flag(cluster, value=True)

        Cluster.update(cluster, {'status': status})

    @classmethod
    def _update_cluster_data(cls, instance):
        cluster = instance.cluster

        if instance.name == consts.TASK_NAMES.deployment:
            if instance.status == consts.TASK_STATUSES.ready:
                # If for some reasons orchestrator
                # didn't send ready status for node
                # we should set it explicitly
                for n in cluster.nodes:
                    if n.status == consts.NODE_STATUSES.deploying:
                        n.status = consts.NODE_STATUSES.ready
                        n.progress = 100

                cls.__update_cluster_status(
                    cluster,
                    consts.CLUSTER_STATUSES.operational,
                    consts.NODE_STATUSES.ready
                )

                Cluster.clear_pending_changes(cluster)

            elif instance.status == consts.CLUSTER_STATUSES.error:
                cls.__update_cluster_status(
                    cluster, consts.CLUSTER_STATUSES.error, None
                )
                q_nodes_to_error = TaskHelper.get_nodes_to_deployment_error(
                    cluster
                )
                cls.__update_nodes_to_error(
                    q_nodes_to_error, error_type=consts.NODE_ERRORS.deploy
                )
        elif instance.name == consts.TASK_NAMES.spawn_vms:
            if instance.status == consts.TASK_STATUSES.ready:
                Cluster.set_vms_created_state(cluster)
            elif instance.status == consts.TASK_STATUSES.error and \
                    not TaskHelper.before_deployment_error(instance):
                cls.__update_cluster_status(
                    cluster, consts.CLUSTER_STATUSES.error, None
                )
        elif instance.name == consts.TASK_NAMES.deploy and \
                instance.status == consts.TASK_STATUSES.error and \
                not TaskHelper.before_deployment_error(instance):
            # We don't want to set cluster status to
            # error because we don't want to lock
            # settings if cluster wasn't deployed

            cls.__update_cluster_status(
                cluster, consts.CLUSTER_STATUSES.error, None
            )

        elif instance.name == consts.TASK_NAMES.provision:
            if instance.status == consts.TASK_STATUSES.ready:
                cls.__update_cluster_status(
                    cluster, consts.CLUSTER_STATUSES.partially_deployed, None
                )
            elif instance.status == consts.TASK_STATUSES.error:
                cls.__update_cluster_status(
                    cluster, consts.CLUSTER_STATUSES.error, None
                )
                q_nodes_to_error = \
                    TaskHelper.get_nodes_to_provisioning_error(cluster)

                cls.__update_nodes_to_error(
                    q_nodes_to_error, error_type=consts.NODE_ERRORS.provision)
        elif instance.name == consts.TASK_NAMES.stop_deployment:
            if instance.status == consts.TASK_STATUSES.error:
                cls.__update_cluster_status(
                    cluster, consts.CLUSTER_STATUSES.error, None
                )
            else:
                cls.__update_cluster_status(
                    cluster, consts.CLUSTER_STATUSES.stopped, None
                )

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

    @classmethod
    def delete(cls, instance, db_deletion=False):
        if db_deletion:
            logger.debug("Delete task: %s", instance.uuid)
            super(Task, cls).delete(instance)
        else:
            logger.debug("Mark task as deleted: %s", instance.uuid)
            cls.update(instance, {'deleted_at': datetime.utcnow()})
            db().commit()

    @classmethod
    def bulk_delete(cls, instance_ids):
        db().query(cls.model).filter(cls.model.id.in_(instance_ids))\
            .update({'deleted_at': datetime.utcnow()},
                    synchronize_session='fetch')


class TaskCollection(NailgunCollection):

    single = Task

    @classmethod
    def get_by_cluster_id(cls, cluster_id):
        if cluster_id == '':
            return cls.filter_by(None, cluster_id=None)\
                      .filter_by(deleted_at=None)
        return cls.filter_by(None, cluster_id=cluster_id)\
                  .filter_by(deleted_at=None)

    @classmethod
    def get_cluster_tasks(cls, cluster_id, names=None):
        query = cls.get_by_cluster_id(cluster_id)
        if isinstance(names, (list, tuple)):
            query = cls.filter_by_list(query, 'name', names)
        query = cls.order_by(query, 'id')
        return query.all()

    @classmethod
    def get_by_name_and_cluster(cls, cluster, names):
        return db().query(cls.single.model).filter_by(
            cluster_id=cluster.id).filter(cls.single.model.name.in_(names))

    @classmethod
    def delete_by_names(cls, cluster, names):
        cls.get_by_name_and_cluster(cluster, names).delete(
            synchronize_session=False)

    @classmethod
    def all_not_deleted(cls):
        return cls.filter_by(None, deleted_at=None)
