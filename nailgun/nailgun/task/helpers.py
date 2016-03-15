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

import datetime
import six
import web

import sqlalchemy as sa
from sqlalchemy.orm import exc

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy.models import Node
from nailgun.db.sqlalchemy.models import Task
from nailgun.errors import errors
from nailgun.logger import logger
from nailgun.statistics.fuel_statistics.tasks_params_white_lists \
    import task_output_white_list


tasks_names_actions_groups_mapping = {
    consts.TASK_NAMES.deploy: "cluster_changes",
    consts.TASK_NAMES.deployment: "cluster_changes",
    consts.TASK_NAMES.provision: "cluster_changes",
    consts.TASK_NAMES.node_deletion: "cluster_changes",
    consts.TASK_NAMES.update: "cluster_changes",
    consts.TASK_NAMES.cluster_deletion: "cluster_changes",
    consts.TASK_NAMES.stop_deployment: "cluster_changes",
    consts.TASK_NAMES.reset_environment: "cluster_changes",

    consts.TASK_NAMES.check_networks: "cluster_checking",
    consts.TASK_NAMES.check_before_deployment: "cluster_checking",
    consts.TASK_NAMES.verify_networks: "cluster_checking",
    consts.TASK_NAMES.check_dhcp: "cluster_checking",
    consts.TASK_NAMES.multicast_verification: "cluster_checking",

    consts.TASK_NAMES.dump: "operations",
    consts.TASK_NAMES.capacity_log: "operations",

    consts.TASK_NAMES.create_stats_user: "statistics",
    consts.TASK_NAMES.remove_stats_user: "statistics"
}


class TaskHelper(object):

    # TODO(aroma): move this function to utils module
    @classmethod
    def calculate_parent_task_progress(cls, subtasks_list):
        return int(
            round(
                sum(
                    [s.weight * s.progress for s
                     in subtasks_list]
                ) /
                sum(
                    [s.weight for s
                     in subtasks_list]
                ), 0)
        )

    # TODO(aroma): move it to utils module
    @classmethod
    def before_deployment_error(cls, task):
        """Checks if there was an error before deployment

        Returns True in case of check_before_deployment
        or check_networks error and if cluster wasn't
        deployed yet
        """
        error_checking_tasks_count = db().query(Task).\
            filter_by(parent_id=task.id).\
            filter_by(status='error').\
            filter(Task.name.in_(
                ['check_before_deployment', 'check_networks'])).count()

        return not task.cluster.is_locked and error_checking_tasks_count

    # TODO(aroma): move this method to utils module
    @classmethod
    def get_nodes_to_provisioning_error(cls, cluster):
        q_nodes_to_error = db().query(Node).\
            filter(Node.cluster == cluster).\
            filter(Node.status.in_(['provisioning']))

        return q_nodes_to_error

    # TODO(aroma): move this method to utils module
    @classmethod
    def get_nodes_to_deployment_error(cls, cluster):
        q_nodes_to_error = db().query(Node).\
            filter(Node.cluster == cluster).\
            filter(Node.status.in_(['deploying']))

        return q_nodes_to_error

    @classmethod
    def recalculate_deployment_task_progress(cls, task):
        cluster_nodes = db().query(Node).filter_by(cluster_id=task.cluster_id)
        nodes_progress = []
        nodes_progress.extend(
            cluster_nodes.filter_by(status='discover').count() * [0])
        nodes_progress.extend(
            cluster_nodes.filter_by(online=False).count() * [100])

        # Progress of provisioned node is 0
        # because deployment not started yet
        nodes_progress.extend(
            cluster_nodes.filter_by(status='provisioned').count() * [0])

        nodes_progress.extend([
            n.progress for n in
            cluster_nodes.filter(
                Node.status.in_(['deploying', 'ready']))])

        if nodes_progress:
            return int(float(sum(nodes_progress)) / len(nodes_progress))

    @classmethod
    def recalculate_provisioning_task_progress(cls, task):
        cluster_nodes = db().query(Node).filter_by(cluster_id=task.cluster_id)
        nodes_progress = [
            n.progress for n in
            cluster_nodes.filter(
                Node.status.in_(['provisioning', 'provisioned']))]

        if nodes_progress:
            return int(float(sum(nodes_progress)) / len(nodes_progress))

    @classmethod
    def nodes_to_delete(cls, cluster):
        return filter(
            lambda n: any([
                n.pending_deletion,
                n.needs_redeletion
            ]),
            cluster.nodes
        )

    # TODO(aroma): considering moving this code to
    # nailgun Cluster object's methods
    @classmethod
    def nodes_to_deploy(cls, cluster, force=False):
        from nailgun import objects  # preventing cycle import error

        nodes_to_deploy = []
        update_required = set()
        update_once = set()
        cluster_roles = set()
        roles_metadata = objects.Cluster.get_roles(cluster)

        for node in cluster.nodes:
            cluster_roles.update(node.roles)

        for node in cluster.nodes:
            valid_node = any([node.pending_addition,
                             node.needs_reprovision,
                             node.needs_redeploy])
            force_node = force and not node.pending_deletion

            if valid_node or force_node:
                nodes_to_deploy.append(node)
                for role_name in node.pending_roles:
                    update_required.update(
                        roles_metadata[role_name].get('update_required', []))
                    if role_name not in cluster_roles:
                        update_once.update(
                            roles_metadata[role_name].get('update_once', []))
        cls.add_required_for_update_nodes(
            cluster, nodes_to_deploy, update_required | update_once)
        if cluster.is_ha_mode:
            return cls.nodes_to_deploy_ha(cluster, nodes_to_deploy)

        return nodes_to_deploy

    @classmethod
    def add_required_for_update_nodes(
            cls, cluster, nodes_to_deploy, update_required):
        """Add nodes that requires update

        :param cluster: Cluster instance
        :param nodes_to_deploy: list of Nodes instance that should be deployed
        :param update_required: set of roles that should be updated
        :returns: None
        """
        for node in cluster.nodes:
            if (node not in nodes_to_deploy and not node.pending_deletion and
                    set(node.roles) & update_required):
                nodes_to_deploy.append(node)

    @classmethod
    def nodes_to_provision(cls, cluster):
        return sorted(filter(
            lambda n: any([
                n.pending_addition,
                n.needs_reprovision
            ]),
            cluster.nodes
        ), key=lambda n: n.id)

    @classmethod
    def nodes_in_provisioning(cls, cluster):
        return sorted(filter(
            lambda n: n.status == 'provisioning',
            cluster.nodes
        ), key=lambda n: n.id)

    @classmethod
    def _node_can_be_updated(cls, node):
        return (node.status in (consts.NODE_STATUSES.ready,
                                consts.NODE_STATUSES.provisioned)) or \
               (node.status == consts.NODE_STATUSES.error
                and node.error_type == consts.NODE_ERRORS.deploy)

    @classmethod
    def nodes_to_upgrade(cls, cluster):
        nodes_to_upgrade = filter(
            lambda n: cls._node_can_be_updated(n),
            cluster.nodes
        )

        if cluster.is_ha_mode:
            return cls.nodes_to_deploy_ha(cluster, nodes_to_upgrade)

        return sorted(nodes_to_upgrade, key=lambda n: n.id)

    @classmethod
    def nodes_to_deploy_ha(cls, cluster, nodes):
        """Get nodes for deployment for ha mode

        * in case of failed controller should be redeployed
          all controllers
        * in case of failed non-controller should be
          redeployed only node which was failed

        If node list has at least one controller we
        filter all controllers from the cluster and
        return them.
        """
        controller_nodes = []

        # if list contain at least one controller
        if cls.__has_controller_nodes(nodes):
            # retrive all controllers from cluster
            controller_nodes = db().query(Node).filter_by(
                cluster_id=cluster.id,
                pending_deletion=False
            ).filter(sa.or_(
                Node.roles.any('controller'),
                Node.pending_roles.any('controller')
            )).order_by(Node.id).all()

        return sorted(set(nodes + controller_nodes),
                      key=lambda node: node.id)

    @classmethod
    def __has_controller_nodes(cls, nodes):
        """Returns True if list of nodes has at least one controller."""
        for node in nodes:
            if 'controller' in set(node.roles + node.pending_roles):
                return True
        return False

    @staticmethod
    def expose_network_check_error_messages(task, result, err_messages):
        if err_messages:
            task.result = result
            db().add(task)
            db().commit()
            full_err_msg = u"\n".join(err_messages)
            raise errors.NetworkCheckError(full_err_msg)

    @classmethod
    def prepare_action_log_kwargs(cls, task):
        """Prepares kwargs dict for ActionLog db model class

        :param task: task instance to be processed
        :returns: kwargs dict for action log creation
        """
        create_kwargs = {
            'task_uuid': task.uuid,
            'cluster_id': task.cluster_id,
            'action_group': tasks_names_actions_groups_mapping[task.name],
            'action_name': task.name,
            'action_type': consts.ACTION_TYPES.nailgun_task,
            'start_timestamp': datetime.datetime.utcnow()
        }

        # actor_id passed from ConnectionMonitor middleware and is
        # needed for binding task execution event with particular
        # actor
        actor_id = None
        try:
            actor_id_field = 'fuel.action.actor_id'
            if hasattr(web.ctx, 'env') and actor_id_field in web.ctx.env:
                # Fetching actor_id from env context
                actor_id = web.ctx.env.get(actor_id_field)
            else:
                # Fetching actor_id from parent task action log
                from nailgun import objects  # preventing cycle import error

                if task.parent_id:
                    parent_task = objects.Task.get_by_uid(task.parent_id)
                    action_log = objects.ActionLog.get_by_kwargs(
                        task_uuid=parent_task.uuid,
                        action_name=parent_task.name)
                    actor_id = action_log.actor_id
        except Exception:
            logger.exception("Extracting of actor_id failed")
        create_kwargs['actor_id'] = actor_id

        additional_info = {
            'parent_task_id': task.parent_id,
            'subtasks_ids': [t.id for t in task.subtasks],
            'operation': task.name
        }
        create_kwargs['additional_info'] = additional_info

        return create_kwargs

    @classmethod
    def sanitize_task_output(cls, task_output, al):

        def sanitize_sub_tree(raw, white_list):
            sanitized = None
            if isinstance(raw, list) and isinstance(white_list, dict):
                sanitized = []
                for item in raw:
                    sanitized.append(sanitize_sub_tree(item, white_list))
            elif isinstance(raw, dict) and isinstance(white_list, dict):
                sanitized = {}
                for key in raw:
                    if key in white_list:
                        if isinstance(white_list[key], dict):
                            sanitized[key] = \
                                sanitize_sub_tree(raw[key], white_list[key])
                        else:
                            sanitized[key] = raw[key]
                    elif "*" in white_list:
                        if isinstance(white_list["*"], dict):
                            sanitized[key] = \
                                sanitize_sub_tree(raw[key], white_list["*"])
                        else:
                            sanitized[key] = raw[key]
            return sanitized

        if al.action_name not in task_output_white_list:
            return None
        white_list = task_output_white_list[al.action_name]
        return sanitize_sub_tree(task_output, white_list)

    @classmethod
    def create_action_log(cls, task):
        """Creates action log

        :param task: SqlAlchemy task object
        :return: SqlAlchemy action_log object
        """
        from nailgun.objects import ActionLog

        try:
            create_kwargs = cls.prepare_action_log_kwargs(task)
            return ActionLog.create(create_kwargs)
        except Exception as e:
            logger.error("create_action_log failed: %s", six.text_type(e))

    @classmethod
    def get_task_cache(cls, task_instance):
        """Retrieve "cache" attritbute from task instance.

        In some cases row that is related to task_instance is deleted
        from db and, since "cache" attribute has marked as deffered,
        SQLAlchemy error occurs.

        :param task_instance: task object to inspect
        :returns: task_instance.cache attribute value or emty dict if
        corresponding row was deleted from db
        """
        task_cache = {}
        try:
            task_cache = task_instance.cache
        except exc.ObjectDeletedError:
            logger.warning("Cache retrieving from task with uuid {0} failed "
                           "due to deletion of corresponding row from db. "
                           "Empty data will be provided for action log "
                           "updating routine.".format(task_instance.uuid))

        return task_cache

    @classmethod
    def update_action_log(cls, task, al_instance=None):
        from nailgun.objects import ActionLog

        try:
            if not al_instance:
                al_instance = ActionLog.get_by_kwargs(task_uuid=task.uuid,
                                                      action_name=task.name)
            # this is needed as status for check_networks task is not set to
            # "ready" in case of success (it is left in status "running") so
            # we do it here manually, there is no such issue with "error"
            # status though.
            set_to_ready_cond = (
                task.name == consts.TASK_NAMES.check_networks
                and task.status == consts.TASK_STATUSES.running
            )
            task_status = consts.TASK_STATUSES.ready if set_to_ready_cond \
                else task.status

            if al_instance:
                task_cache = cls.get_task_cache(task)
                update_data = {
                    "end_timestamp": datetime.datetime.utcnow(),
                    "additional_info": {
                        "ended_with_status": task_status,
                        "message": "",
                        "output": cls.sanitize_task_output(task_cache,
                                                           al_instance)
                    }
                }
                ActionLog.update(al_instance, update_data)
        except Exception as e:
            logger.error("update_action_log failed: %s", six.text_type(e))

    @classmethod
    def set_ready_if_not_finished(cls, task):
        if task.status in (consts.TASK_STATUSES.pending,
                           consts.TASK_STATUSES.running):
            task.status = consts.TASK_STATUSES.ready
        cls.update_action_log(task)
