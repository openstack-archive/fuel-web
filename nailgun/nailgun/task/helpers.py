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

import os
import shutil

from sqlalchemy import or_

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy.models import IPAddr
from nailgun.db.sqlalchemy.models import Node
from nailgun.db.sqlalchemy.models import Task
from nailgun.errors import errors
from nailgun.logger import logger
from nailgun.settings import settings


class TaskHelper(object):

    # TODO(aroma): move it to utils module
    @classmethod
    def prepare_syslog_dir(cls, node, admin_net_id, prefix=None):
        logger.debug("Preparing syslog directories for node: %s", node.fqdn)
        if not prefix:
            prefix = settings.SYSLOG_DIR
        logger.debug("prepare_syslog_dir prefix=%s", prefix)

        old = os.path.join(prefix, str(node.ip))
        bak = os.path.join(prefix, "%s.bak" % str(node.fqdn))
        new = os.path.join(prefix, str(node.fqdn))

        links = map(
            lambda i: os.path.join(prefix, i.ip_addr),
            db().query(IPAddr.ip_addr).
            filter_by(node=node.id).
            filter_by(network=admin_net_id).all()
        )

        logger.debug("prepare_syslog_dir old=%s", old)
        logger.debug("prepare_syslog_dir new=%s", new)
        logger.debug("prepare_syslog_dir bak=%s", bak)
        logger.debug("prepare_syslog_dir links=%s", str(links))

        # backup directory if it exists
        if os.path.isdir(new):
            logger.debug("New %s already exists. Trying to backup", new)
            if os.path.islink(bak):
                logger.debug("Bak %s already exists and it is link. "
                             "Trying to unlink", bak)
                os.unlink(bak)
            elif os.path.isdir(bak):
                logger.debug("Bak %s already exists and it is directory. "
                             "Trying to remove", bak)
                shutil.rmtree(bak)
            os.rename(new, bak)

        # rename bootstrap directory into fqdn
        if os.path.islink(old):
            logger.debug("Old %s exists and it is link. "
                         "Trying to unlink", old)
            os.unlink(old)
        if os.path.isdir(old):
            logger.debug("Old %s exists and it is directory. "
                         "Trying to rename into %s", old, new)
            os.rename(old, new)
        else:
            logger.debug("Creating %s", new)
            os.makedirs(new)

        # creating symlinks
        for l in links:
            if os.path.islink(l) or os.path.isfile(l):
                logger.debug("%s already exists. "
                             "Trying to unlink", l)
                os.unlink(l)
            if os.path.isdir(l):
                logger.debug("%s already exists and it directory. "
                             "Trying to remove", l)
                shutil.rmtree(l)
            logger.debug("Creating symlink %s -> %s", l, new)
            os.symlink(str(node.fqdn), l)

        os.system("/usr/bin/pkill -HUP rsyslog")

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
        """Returns True in case of check_before_deployment
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
    def nodes_to_deploy(cls, cluster):
        nodes_to_deploy = sorted(filter(
            lambda n: any([
                n.pending_addition,
                n.needs_reprovision,
                n.needs_redeploy
            ]),
            cluster.nodes
        ), key=lambda n: n.id)

        if cluster.is_ha_mode:
            return cls.__nodes_to_deploy_ha(cluster, nodes_to_deploy)

        return nodes_to_deploy

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
            return cls.__nodes_to_deploy_ha(cluster, nodes_to_upgrade)

        return sorted(nodes_to_upgrade, key=lambda n: n.id)

    @classmethod
    def __nodes_to_deploy_ha(cls, cluster, nodes):
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
            controller_nodes = db().query(Node). \
                filter(or_(
                    Node.role_list.any(name='controller'),
                    Node.pending_role_list.any(name='controller'),
                    Node.role_list.any(name='primary-controller'),
                    Node.pending_role_list.any(name='primary-controller')
                )). \
                filter(Node.cluster == cluster). \
                filter(False == Node.pending_deletion). \
                order_by(Node.id).all()

        return sorted(set(nodes + controller_nodes),
                      key=lambda node: node.id)

    @classmethod
    def __has_controller_nodes(cls, nodes):
        """Returns True if list of nodes has
        at least one controller.
        """
        for node in nodes:
            if 'controller' in node.all_roles or \
               'primary-controller' in node.all_roles:
                return True
        return False

    @classmethod
    def set_error(cls, task_uuid, message):
        cls.update_task_status(
            task_uuid,
            status="error",
            progress=100,
            msg=str(message))

    @staticmethod
    def expose_network_check_error_messages(task, result, err_messages):
        if err_messages:
            task.result = result
            db().add(task)
            db().commit()
            full_err_msg = u"\n".join(err_messages)
            raise errors.NetworkCheckError(full_err_msg)
