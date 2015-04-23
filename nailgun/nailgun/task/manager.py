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

import traceback

from oslo.serialization import jsonutils

from nailgun.objects.serializers.network_configuration \
    import NeutronNetworkConfigurationSerializer
from nailgun.objects.serializers.network_configuration \
    import NovaNetworkConfigurationSerializer

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy.models import Cluster
from nailgun.db.sqlalchemy.models import Node
from nailgun.db.sqlalchemy.models import Task
from nailgun.errors import errors
from nailgun.logger import logger
from nailgun import objects
import nailgun.rpc as rpc
from nailgun.task import task as tasks
from nailgun.task.task import TaskHelper
from nailgun.utils import mule


class TaskManager(object):

    def __init__(self, cluster_id=None):
        if cluster_id:
            self.cluster = db().query(Cluster).get(cluster_id)

    def _call_silently(self, task, instance, *args, **kwargs):
        # create action_log for task
        al = TaskHelper.create_action_log(task)

        method = getattr(instance, kwargs.pop('method_name', 'execute'))
        if task.status == consts.TASK_STATUSES.error:
            TaskHelper.update_action_log(task, al)
            return
        try:
            to_return = method(task, *args, **kwargs)

            # update action_log instance for task
            # for asynchronous task it will be not final update
            # as they also are updated in rpc receiver
            TaskHelper.update_action_log(task, al)

            return to_return
        except Exception as exc:
            err = str(exc)
            if any([
                not hasattr(exc, "log_traceback"),
                hasattr(exc, "log_traceback") and exc.log_traceback
            ]):
                logger.error(traceback.format_exc())

            # update task entity with given data
            data = {'status': 'error',
                    'progress': 100,
                    'message': err}
            objects.Task.update(task, data)

            TaskHelper.update_action_log(task, al)

    def check_running_task(self, task_name):
        current_tasks = db().query(Task).filter_by(
            name=task_name
        )
        for task in current_tasks:
            if task.status == "running":
                raise errors.DumpRunning()
            elif task.status in ("ready", "error"):
                db().delete(task)
                db().commit()

    def serialize_network_cfg(self, cluster):
        serializer = {'nova_network': NovaNetworkConfigurationSerializer,
                      'neutron': NeutronNetworkConfigurationSerializer}
        return serializer[cluster.net_provider].serialize_for_cluster(cluster)

    def _adjust_nodes_lists_on_controller_removing(self, nodes_to_delete,
                                                   nodes_to_deploy):
        """In case of deleting controller(s) adds other controller(s)
        to nodes_to_deploy
        :param nodes_to_delete: list of nodes to be deleted
        :param nodes_to_deploy: list of nodes to be deployed
        :return:
        """
        if getattr(self, 'cluster', None) is None:
            return

        controllers_ids_to_delete = set([n.id for n in nodes_to_delete
                                         if 'controller' in n.roles])
        if controllers_ids_to_delete:
            ids_to_deploy = set([n.id for n in nodes_to_deploy])
            controllers_to_deploy = set(
                filter(lambda n: (n.id not in controllers_ids_to_delete
                                  and n.id not in ids_to_deploy
                                  and 'controller' in n.roles),
                       self.cluster.nodes))
            nodes_to_deploy.extend(controllers_to_deploy)


class ApplyChangesTaskManager(TaskManager):

    def _lock_required_tasks(self):
        names = (
            consts.TASK_NAMES.deploy,
            consts.TASK_NAMES.stop_deployment,
            consts.TASK_NAMES.reset_environment
        )
        return objects.TaskCollection.lock_cluster_tasks(
            cluster_id=self.cluster.id, names=names
        )

    def _remove_obsolete_tasks(self):
        locked_tasks = self._lock_required_tasks()
        current_tasks = objects.TaskCollection.filter_by(
            locked_tasks,
            name=consts.TASK_NAMES.deploy
        )
        # locking cluster
        objects.Cluster.get_by_uid(
            self.cluster.id,
            fail_if_not_found=True,
            lock_for_update=True
        )

        for task in current_tasks:
            if task.status == consts.TASK_STATUSES.running:
                db().commit()
                raise errors.DeploymentAlreadyStarted()
            elif task.status in (consts.TASK_STATUSES.ready,
                                 consts.TASK_STATUSES.error):
                db().delete(task)
        db().flush()

        obsolete_tasks = objects.TaskCollection.filter_by_list(
            locked_tasks,
            'name',
            (consts.TASK_NAMES.stop_deployment,
             consts.TASK_NAMES.reset_environment)
        )
        for task in obsolete_tasks:
            db().delete(task)
        db().flush()

    def execute(self):
        logger.info(
            u"Trying to start deployment at cluster '{0}'".format(
                self.cluster.name or self.cluster.id
            )
        )

        network_info = self.serialize_network_cfg(self.cluster)
        logger.info(
            u"Network info:\n{0}".format(
                jsonutils.dumps(network_info, indent=4)
            )
        )

        self._remove_obsolete_tasks()

        supertask = Task(name=consts.TASK_NAMES.deploy, cluster=self.cluster)
        db().add(supertask)

        nodes_to_delete = TaskHelper.nodes_to_delete(self.cluster)
        nodes_to_deploy = TaskHelper.nodes_to_deploy(self.cluster)
        nodes_to_provision = TaskHelper.nodes_to_provision(self.cluster)

        if not any([nodes_to_provision, nodes_to_deploy, nodes_to_delete]):
            db().rollback()
            raise errors.WrongNodeStatus("No changes to deploy")

        # we should have task committed for processing in other threads
        db().commit()
        TaskHelper.create_action_log(supertask)

        mule.call_task_manager_async(
            self.__class__,
            '_execute_async',
            self.cluster.id,
            supertask.id
        )

        return supertask

    def _execute_async(self, supertask_id):
        """Function for execute task in the mule
        :param supertask_id: id of parent task
        """
        logger.info(u"ApplyChangesTask: execute async starting for task %s",
                    supertask_id)

        supertask = objects.Task.get_by_uid(supertask_id)

        try:
            self._execute_async_content(supertask)
        except Exception as e:
            logger.exception('Error occurred when running task')
            data = {
                'status': consts.TASK_STATUSES.error,
                'progress': 100,
                'message': u'Error occurred when running task: {0}'.format(
                    e.message),
            }
            objects.Task.update(supertask, data)
            db().commit()

    def _execute_async_content(self, supertask):
        """Processes supertask async in mule
        :param supertask: SqlAlchemy task object
        """

        nodes_to_delete = TaskHelper.nodes_to_delete(self.cluster)
        nodes_to_deploy = TaskHelper.nodes_to_deploy(self.cluster)
        nodes_to_provision = TaskHelper.nodes_to_provision(self.cluster)

        self._adjust_nodes_lists_on_controller_removing(nodes_to_delete,
                                                        nodes_to_deploy)

        task_messages = []
        # Run validation if user didn't redefine
        # provisioning and deployment information

        if (not objects.Cluster.get_provisioning_info(self.cluster) and
                not objects.Cluster.get_deployment_info(self.cluster)):
            try:
                self.check_before_deployment(supertask)
            except errors.CheckBeforeDeploymentError:
                db().commit()
                return

        task_deletion, task_provision, task_deployment = None, None, None

        if nodes_to_delete:
            objects.TaskCollection.lock_cluster_tasks(self.cluster.id)
            # For more accurate progress calculation
            task_weight = 0.4
            task_deletion = supertask.create_subtask(
                consts.TASK_NAMES.node_deletion,
                weight=task_weight)
            logger.debug("Launching deletion task: %s", task_deletion.uuid)

            self._call_silently(
                task_deletion,
                tasks.DeletionTask,
                tasks.DeletionTask.get_task_nodes_for_cluster(self.cluster))
            # we should have task committed for processing in other threads
            db().commit()

        if nodes_to_provision:
            objects.TaskCollection.lock_cluster_tasks(self.cluster.id)
            # updating nodes
            nodes_to_provision = objects.NodeCollection.lock_nodes(
                nodes_to_provision
            )
            objects.NodeCollection.update_slave_nodes_fqdn(nodes_to_provision)
            logger.debug("There are nodes to provision: %s",
                         " ".join([n.fqdn for n in nodes_to_provision]))

            # For more accurate progress calulation
            task_weight = 0.4
            task_provision = supertask.create_subtask(
                consts.TASK_NAMES.provision,
                weight=task_weight)

            # we should have task committed for processing in other threads
            db().commit()
            provision_message = self._call_silently(
                task_provision,
                tasks.ProvisionTask,
                nodes_to_provision,
                method_name='message'
            )

            task_provision = objects.Task.get_by_uid(
                task_provision.id,
                fail_if_not_found=True,
                lock_for_update=True
            )
            # if failed to generate task message for orchestrator
            # then task is already set to error
            if task_provision.status == consts.TASK_STATUSES.error:
                db().rollback()
                return

            task_provision.cache = provision_message
            db().commit()
            task_messages.append(provision_message)

        if nodes_to_deploy:
            objects.TaskCollection.lock_cluster_tasks(self.cluster.id)
            # locking nodes before updating
            objects.NodeCollection.lock_nodes(nodes_to_deploy)
            # updating nodes
            objects.NodeCollection.update_slave_nodes_fqdn(nodes_to_deploy)
            logger.debug("There are nodes to deploy: %s",
                         " ".join([n.fqdn for n in nodes_to_deploy]))
            task_deployment = supertask.create_subtask(
                consts.TASK_NAMES.deployment)

            # we should have task committed for processing in other threads
            db().commit()
            deployment_message = self._call_silently(
                task_deployment,
                tasks.DeploymentTask,
                nodes_to_deploy,
                method_name='message'
            )

            task_deployment = objects.Task.get_by_uid(
                task_deployment.id,
                fail_if_not_found=True,
                lock_for_update=True
            )
            # if failed to generate task message for orchestrator
            # then task is already set to error
            if task_deployment.status == consts.TASK_STATUSES.error:
                db().rollback()
                return

            task_deployment.cache = deployment_message
            db().commit()
            task_messages.append(deployment_message)

        if nodes_to_provision:
            nodes_to_provision = objects.NodeCollection.lock_nodes(
                nodes_to_provision
            )
            for node in nodes_to_provision:
                node.status = consts.NODE_STATUSES.provisioning
            db().commit()

        objects.Cluster.get_by_uid(
            self.cluster.id,
            fail_if_not_found=True,
            lock_for_update=True
        )
        self.cluster.status = consts.CLUSTER_STATUSES.deployment
        db().add(self.cluster)
        db().commit()

        if task_messages:
            rpc.cast('naily', task_messages)

        logger.debug(
            u"Deployment: task to deploy cluster '{0}' is {1}".format(
                self.cluster.name or self.cluster.id,
                supertask.uuid
            )
        )

    def check_before_deployment(self, supertask):
        """Performs checks before deployment
        :param supertask: task SqlAlchemy object
        """
        # checking admin intersection with untagged
        network_info = self.serialize_network_cfg(self.cluster)
        network_info["networks"] = [
            n for n in network_info["networks"] if n["name"] != "fuelweb_admin"
        ]

        check_networks = supertask.create_subtask(
            consts.TASK_NAMES.check_networks)

        self._call_silently(
            check_networks,
            tasks.CheckNetworksTask,
            data=network_info,
            check_admin_untagged=True
        )

        if check_networks.status == consts.TASK_STATUSES.error:
            logger.warning(
                "Checking networks failed: %s", check_networks.message
            )
            raise errors.CheckBeforeDeploymentError(check_networks.message)
        TaskHelper.set_ready_if_not_finished(check_networks)
        db().delete(check_networks)
        db().refresh(supertask)
        db().flush()

        # checking prerequisites
        check_before = supertask.create_subtask(
            consts.TASK_NAMES.check_before_deployment
        )
        logger.debug("Checking prerequisites task: %s", check_before.uuid)

        self._call_silently(
            check_before,
            tasks.CheckBeforeDeploymentTask
        )

        # if failed to check prerequisites
        # then task is already set to error
        if check_before.status == consts.TASK_STATUSES.error:
            logger.warning(
                "Checking prerequisites failed: %s", check_before.message
            )
            raise errors.CheckBeforeDeploymentError(check_before.message)
        logger.debug(
            "Checking prerequisites is successful, starting deployment..."
        )
        TaskHelper.set_ready_if_not_finished(check_before)
        db().delete(check_before)
        db().refresh(supertask)
        db().flush()


class ProvisioningTaskManager(TaskManager):

    def execute(self, nodes_to_provision):
        """Run provisioning task on specified nodes
        """
        # locking nodes
        nodes_ids = [node.id for node in nodes_to_provision]
        nodes = objects.NodeCollection.filter_by_list(
            None,
            'id',
            nodes_ids,
            order_by='id'
        )
        objects.NodeCollection.lock_for_update(nodes).all()

        objects.NodeCollection.update_slave_nodes_fqdn(nodes_to_provision)
        logger.debug('Nodes to provision: {0}'.format(
            ' '.join([n.fqdn for n in nodes_to_provision])))

        task_provision = Task(name=consts.TASK_NAMES.provision,
                              cluster=self.cluster)
        db().add(task_provision)
        db().commit()

        provision_message = self._call_silently(
            task_provision,
            tasks.ProvisionTask,
            nodes_to_provision,
            method_name='message'
        )

        task_provision = objects.Task.get_by_uid(
            task_provision.id,
            fail_if_not_found=True,
            lock_for_update=True
        )
        task_provision.cache = provision_message
        objects.NodeCollection.lock_for_update(nodes).all()

        for node in nodes_to_provision:
            node.pending_addition = False
            node.status = consts.NODE_STATUSES.provisioning
            node.progress = 0

        db().commit()

        rpc.cast('naily', provision_message)

        return task_provision


class DeploymentTaskManager(TaskManager):

    def execute(self, nodes_to_deployment, deployment_tasks=None):
        deployment_tasks = deployment_tasks or []

        # locking nodes for update
        objects.NodeCollection.lock_nodes(nodes_to_deployment)
        objects.NodeCollection.update_slave_nodes_fqdn(nodes_to_deployment)

        logger.debug('Nodes to deploy: {0}'.format(
            ' '.join([n.fqdn for n in nodes_to_deployment])))
        task_deployment = Task(
            name=consts.TASK_NAMES.deployment, cluster=self.cluster)
        db().add(task_deployment)

        deployment_message = self._call_silently(
            task_deployment,
            tasks.DeploymentTask,
            nodes_to_deployment,
            deployment_tasks=deployment_tasks,
            method_name='message')

        db().refresh(task_deployment)

        # locking task
        task_deployment = objects.Task.get_by_uid(
            task_deployment.id,
            fail_if_not_found=True,
            lock_for_update=True
        )
        # locking nodes
        objects.NodeCollection.lock_nodes(nodes_to_deployment)

        task_deployment.cache = deployment_message

        for node in nodes_to_deployment:
            node.status = 'deploying'
            node.progress = 0

        db().commit()

        rpc.cast('naily', deployment_message)

        return task_deployment


class StopDeploymentTaskManager(TaskManager):

    def execute(self):
        # locking tasks for processing
        names = (
            consts.TASK_NAMES.deploy,
            consts.TASK_NAMES.stop_deployment,
            consts.TASK_NAMES.deployment,
            consts.TASK_NAMES.provision
        )
        objects.TaskCollection.lock_cluster_tasks(
            self.cluster.id,
            names=names
        )

        stop_running = objects.TaskCollection.filter_by(
            None,
            cluster_id=self.cluster.id,
            name=consts.TASK_NAMES.stop_deployment,
        )
        stop_running = objects.TaskCollection.order_by(
            stop_running, 'id'
        ).first()

        if stop_running:
            if stop_running.status == consts.TASK_STATUSES.running:
                raise errors.StopAlreadyRunning(
                    "Stopping deployment task "
                    "is already launched"
                )
            else:
                db().delete(stop_running)
                db().flush()

        deployment_task = objects.TaskCollection.filter_by(
            None,
            cluster_id=self.cluster.id,
            name=consts.TASK_NAMES.deployment,
        )
        deployment_task = objects.TaskCollection.order_by(
            deployment_task, 'id'
        ).first()

        provisioning_task = objects.TaskCollection.filter_by(
            None,
            cluster_id=self.cluster.id,
            name=consts.TASK_NAMES.provision,
        )
        provisioning_task = objects.TaskCollection.order_by(
            provisioning_task, 'id'
        ).first()

        if not deployment_task and not provisioning_task:
            db().rollback()
            raise errors.DeploymentNotRunning(
                u"Nothing to stop - deployment is "
                u"not running on environment '{0}'".format(
                    self.cluster.id
                )
            )

        # Updating action logs for deploy task
        deploy_task = objects.TaskCollection.filter_by(
            None,
            cluster_id=self.cluster.id,
            name=consts.TASK_NAMES.deploy
        )
        deploy_task = objects.TaskCollection.order_by(
            deploy_task, 'id').first()
        if deploy_task:
            TaskHelper.set_ready_if_not_finished(deploy_task)

        task = Task(
            name=consts.TASK_NAMES.stop_deployment,
            cluster=self.cluster
        )
        db().add(task)
        db().commit()
        self._call_silently(
            task,
            tasks.StopDeploymentTask,
            deploy_task=deployment_task,
            provision_task=provisioning_task
        )
        return task


class ResetEnvironmentTaskManager(TaskManager):

    def execute(self):
        deploy_running = db().query(Task).filter_by(
            cluster=self.cluster,
            name=consts.TASK_NAMES.deploy,
            status='running'
        ).first()
        if deploy_running:
            raise errors.DeploymentAlreadyStarted(
                u"Can't reset environment '{0}' when "
                u"deployment is running".format(
                    self.cluster.id
                )
            )

        obsolete_tasks = db().query(Task).filter_by(
            cluster_id=self.cluster.id,
        ).filter(
            Task.name.in_([
                consts.TASK_NAMES.deploy,
                consts.TASK_NAMES.deployment,
                consts.TASK_NAMES.stop_deployment
            ])
        )
        for task in obsolete_tasks:
            db().delete(task)
        db().commit()

        task = Task(
            name=consts.TASK_NAMES.reset_environment,
            cluster=self.cluster
        )
        db().add(task)
        db.commit()
        self._call_silently(
            task,
            tasks.ResetEnvironmentTask
        )
        return task


class UpdateEnvironmentTaskManager(TaskManager):

    def execute(self):
        if not self.cluster.pending_release_id:
            raise errors.InvalidReleaseId(
                u"Can't update environment '{0}' when "
                u"new release Id is invalid".format(self.cluster.name))

        running_tasks = db().query(Task).filter_by(
            cluster_id=self.cluster.id,
            status='running'
        ).filter(
            Task.name.in_([
                consts.TASK_NAMES.deploy,
                consts.TASK_NAMES.deployment,
                consts.TASK_NAMES.reset_environment,
                consts.TASK_NAMES.stop_deployment
            ])
        )
        if running_tasks.first():
            raise errors.TaskAlreadyRunning(
                u"Can't update environment '{0}' when "
                u"other task is running".format(
                    self.cluster.id
                )
            )

        nodes_to_change = TaskHelper.nodes_to_upgrade(self.cluster)
        objects.NodeCollection.update_slave_nodes_fqdn(nodes_to_change)
        logger.debug('Nodes to update: {0}'.format(
            ' '.join([n.fqdn for n in nodes_to_change])))
        task_update = Task(name=consts.TASK_NAMES.update, cluster=self.cluster)
        db().add(task_update)
        self.cluster.status = 'update'
        db().flush()

        deployment_message = self._call_silently(
            task_update,
            tasks.UpdateTask,
            nodes_to_change,
            method_name='message')

        db().refresh(task_update)

        for node in nodes_to_change:
            node.status = 'deploying'
            node.progress = 0

        db().commit()
        rpc.cast('naily', deployment_message)

        return task_update


class CheckNetworksTaskManager(TaskManager):

    def execute(self, data, check_admin_untagged=False):
        locked_tasks = objects.TaskCollection.filter_by(
            None,
            cluster_id=self.cluster.id,
            name=consts.TASK_NAMES.check_networks
        )
        locked_tasks = objects.TaskCollection.order_by(locked_tasks, 'id')
        check_networks = objects.TaskCollection.lock_for_update(
            locked_tasks
        ).first()
        if check_networks:
            TaskHelper.set_ready_if_not_finished(check_networks)
            db().delete(check_networks)
            db().flush()

        task = Task(
            name=consts.TASK_NAMES.check_networks,
            cluster=self.cluster
        )
        db().add(task)
        db().commit()
        self._call_silently(
            task,
            tasks.CheckNetworksTask,
            data,
            check_admin_untagged
        )

        task = objects.Task.get_by_uid(
            task.id,
            fail_if_not_found=True,
            lock_for_update=True
        )
        if task.status == consts.TASK_STATUSES.running:
            # update task status with given data
            data = {'status': consts.TASK_STATUSES.ready, 'progress': 100}
            objects.Task.update(task, data)
        db().commit()
        return task


class VerifyNetworksTaskManager(TaskManager):

    _blocking_statuses = (
        consts.CLUSTER_STATUSES.deployment,
        consts.CLUSTER_STATUSES.update,
    )

    def remove_previous_task(self):
        locked_tasks = objects.TaskCollection.filter_by(
            None,
            cluster_id=self.cluster.id
        )
        locked_tasks = objects.TaskCollection.filter_by_list(
            locked_tasks,
            'name',
            (consts.TASK_NAMES.check_networks,
             consts.TASK_NAMES.verify_networks),
            order_by='id'
        )
        locked_tasks = objects.TaskCollection.lock_for_update(
            locked_tasks
        ).all()

        check_networks = objects.TaskCollection.filter_by(
            locked_tasks,
            name=consts.TASK_NAMES.check_networks
        )
        check_networks = list(check_networks)

        if check_networks:
            db().delete(check_networks[0])
            db().flush()

        verification_tasks = objects.TaskCollection.filter_by(
            locked_tasks,
            name=consts.TASK_NAMES.verify_networks
        )
        verification_tasks = list(verification_tasks)

        # TODO(pkaminski): this code shouldn't be required at all
        if verification_tasks:
            ver_task = verification_tasks[0]
            if ver_task.status == consts.TASK_STATUSES.running:
                raise errors.CantRemoveOldVerificationTask()
            for subtask in ver_task.subtasks:
                db().delete(subtask)
            db().delete(ver_task)
            db().flush()

    def execute(self, nets, vlan_ids):
        self.remove_previous_task()

        task = Task(
            name=consts.TASK_NAMES.check_networks,
            cluster=self.cluster
        )

        if len([n for n in self.cluster.nodes if n.online]) < 2:
            task.status = consts.TASK_STATUSES.error
            task.progress = 100
            task.message = ('At least two online nodes are required to be '
                            'in the environment for network verification.')
            db().add(task)
            db().commit()
            return task

        if len(self.cluster.node_groups) > 1:
            task.status = consts.TASK_STATUSES.error
            task.progress = 100
            task.message = ('Network verification is disabled for '
                            'environments containing more than one node '
                            'group.')
            db().add(task)
            db().commit()
            return task

        if self.cluster.status in self._blocking_statuses:
            task.status = consts.TASK_STATUSES.error
            task.progress = 100
            task.message = (
                "Environment is not ready to run network verification "
                "because it is in '{0}' state.".format(self.cluster.status)
            )
            db().add(task)
            db().commit()
            return task

        db().add(task)
        db().commit()

        self._call_silently(
            task,
            tasks.CheckNetworksTask,
            data=nets,
            check_admin_untagged=True
        )
        db().refresh(task)

        if task.status != consts.TASK_STATUSES.error:
            # this one is connected with UI issues - we need to
            # separate if error happened inside nailgun or somewhere
            # in the orchestrator, and UI does it by task name.
            task.name = consts.TASK_NAMES.verify_networks
            verify_task = tasks.VerifyNetworksTask(task, vlan_ids)

            if tasks.CheckDhcpTask.enabled(self.cluster):
                dhcp_subtask = objects.task.Task.create_subtask(
                    task, name=consts.TASK_NAMES.check_dhcp)
                verify_task.add_subtask(
                    tasks.CheckDhcpTask(dhcp_subtask, vlan_ids))

            if tasks.MulticastVerificationTask.enabled(self.cluster):
                multicast = objects.task.Task.create_subtask(
                    task, name=consts.TASK_NAMES.multicast_verification)
                verify_task.add_subtask(
                    tasks.MulticastVerificationTask(multicast))

            db().commit()
            self._call_silently(task, verify_task)

        return task


class ClusterDeletionManager(TaskManager):

    def execute(self):
        # locking required tasks
        locked_tasks = objects.TaskCollection.lock_cluster_tasks(
            self.cluster.id
        )
        # locking cluster
        objects.Cluster.get_by_uid(
            self.cluster.id,
            fail_if_not_found=True,
            lock_for_update=True
        )
        # locking nodes
        nodes = objects.NodeCollection.filter_by(
            None,
            cluster_id=self.cluster.id
        )
        nodes = objects.NodeCollection.order_by(nodes, 'id')
        objects.NodeCollection.lock_for_update(nodes).all()

        current_cluster_tasks = objects.TaskCollection.filter_by_list(
            locked_tasks,
            'name',
            (consts.TASK_NAMES.cluster_deletion,)
        )

        deploy_running = objects.TaskCollection.filter_by(
            None,
            cluster_id=self.cluster.id,
            name=consts.TASK_NAMES.deploy,
            status=consts.TASK_STATUSES.running
        )
        deploy_running = objects.TaskCollection.order_by(
            deploy_running,
            'id'
        ).first()
        if deploy_running:
            logger.error(
                u"Deleting cluster '{0}' "
                "while deployment is still running".format(
                    self.cluster.name
                )
            )
            # Updating action logs for deploy task
            TaskHelper.set_ready_if_not_finished(deploy_running)

        logger.debug("Removing cluster tasks")
        for task in current_cluster_tasks:
            if task.status == consts.TASK_STATUSES.running:
                db().rollback()
                raise errors.DeletionAlreadyStarted()
            elif task.status in (consts.TASK_STATUSES.ready,
                                 consts.TASK_STATUSES.error):
                for subtask in task.subtasks:
                    db().delete(subtask)
                db().delete(task)
        db().flush()

        logger.debug("Labeling cluster nodes to delete")
        for node in self.cluster.nodes:
            node.pending_deletion = True
            db().add(node)
        db().flush()

        self.cluster.status = consts.CLUSTER_STATUSES.remove
        db().add(self.cluster)

        logger.debug("Creating cluster deletion task")
        task = Task(name=consts.TASK_NAMES.cluster_deletion,
                    cluster=self.cluster)
        db().add(task)
        db().commit()
        self._call_silently(
            task,
            tasks.ClusterDeletionTask
        )
        return task


class DumpTaskManager(TaskManager):

    def execute(self, conf=None):
        logger.info("Trying to start dump_environment task")
        self.check_running_task(consts.TASK_NAMES.dump)

        task = Task(name=consts.TASK_NAMES.dump)
        db().add(task)
        db().flush()
        self._call_silently(
            task,
            tasks.DumpTask,
            conf=conf
        )
        return task


class GenerateCapacityLogTaskManager(TaskManager):

    def execute(self):
        logger.info("Trying to start capacity_log task")
        self.check_running_task(consts.TASK_NAMES.capacity_log)

        task = Task(name=consts.TASK_NAMES.capacity_log)
        db().add(task)
        db().commit()
        self._call_silently(
            task,
            tasks.GenerateCapacityLogTask)
        return task


class NodeDeletionTaskManager(TaskManager):

    def verify_nodes_with_cluster(self, nodes):
        """Make sure that task.cluster is the same as all nodes' cluster

        :param nodes:
        :return: bool
        """
        cluster_id = None
        if hasattr(self, 'cluster'):
            cluster_id = self.cluster.id

        invalid_nodes = []
        for node in nodes:
            if node.cluster_id != cluster_id:
                invalid_nodes.append(node)

        if invalid_nodes:
            db().rollback()
            raise errors.InvalidData(
                "Invalid data -- nodes' cluster_ids {0} do not match "
                "cluster's id {1}".format(
                    [node.id for node in invalid_nodes], cluster_id)
            )

    def execute(self, nodes_to_delete, mclient_remove=True):
        cluster_id = None
        if hasattr(self, 'cluster'):
            cluster_id = self.cluster.id
            objects.TaskCollection.lock_cluster_tasks(cluster_id)

        logger.info("Trying to execute node deletion task with nodes %s",
                    ', '.join(str(node.id) for node in nodes_to_delete))

        self.verify_nodes_with_cluster(nodes_to_delete)
        objects.NodeCollection.lock_nodes(nodes_to_delete)

        if cluster_id is None:
            # DeletionTask operates on cluster's nodes.
            # Nodes that are not in cluster are simply deleted.

            Node.delete_by_ids([n.id for n in nodes_to_delete])
            db().flush()

            task = Task(name=consts.TASK_NAMES.node_deletion,
                        progress=100,
                        status=consts.TASK_STATUSES.ready)
            db().add(task)
            db().commit()

            return task

        task = Task(name=consts.TASK_NAMES.node_deletion,
                    cluster=self.cluster)
        db().add(task)
        for node in nodes_to_delete:
            objects.Node.update(node,
                                {'status': consts.NODE_STATUSES.removing})

        nodes_to_deploy = []
        self._adjust_nodes_lists_on_controller_removing(nodes_to_delete,
                                                        nodes_to_deploy)

        if nodes_to_deploy:
            objects.NodeCollection.lock_nodes(nodes_to_deploy)
            # updating nodes
            objects.NodeCollection.update_slave_nodes_fqdn(nodes_to_deploy)
            logger.debug("There are nodes to deploy: %s",
                         " ".join([n.fqdn for n in nodes_to_deploy]))
            task_deployment = task.create_subtask(
                consts.TASK_NAMES.deployment)

            deployment_message = self._call_silently(
                task_deployment,
                tasks.DeploymentTask,
                nodes_to_deploy,
                method_name='message'
            )
            db().commit()

            # if failed to generate task message for orchestrator
            # then task is already set to error
            if task_deployment.status == consts.TASK_STATUSES.error:
                return task_deployment

            rpc.cast('naily', [deployment_message])

        db().commit()

        self._call_silently(
            task,
            tasks.DeletionTask,
            nodes=tasks.DeletionTask.prepare_nodes_for_task(
                nodes_to_delete, mclient_remove=mclient_remove))

        return task
