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
from distutils.version import StrictVersion
import traceback

from oslo_serialization import jsonutils

from nailgun.objects.serializers.network_configuration \
    import NeutronNetworkConfigurationSerializer
from nailgun.objects.serializers.network_configuration \
    import NovaNetworkConfigurationSerializer

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy.models import Cluster
from nailgun.db.sqlalchemy.models import Task
from nailgun.errors import errors
from nailgun.logger import logger
from nailgun import notifier
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
        except errors.NoChanges as e:
            self._finish_task(task, al, consts.TASK_STATUSES.ready, str(e))
        except Exception as exc:
            if any([
                not hasattr(exc, "log_traceback"),
                hasattr(exc, "log_traceback") and exc.log_traceback
            ]):
                logger.error(traceback.format_exc())
            self._finish_task(task, al, consts.TASK_STATUSES.error, str(exc))

    def _finish_task(self, task, log_item, status, message):
        data = {'status': status, 'progress': 100, 'message': message}
        # update task entity with given data
        objects.Task.update(task, data)
        # NOTE(romcheg): Flushing the data is required to unlock
        # tasks in order to temporary fix issues with
        # the deadlock detection query in tests and let the tests pass.
        # TODO(akislitsky): Get rid of this flush as soon as
        # task locking issues are resolved.
        db().flush()
        TaskHelper.update_action_log(task, log_item)

        db().commit()

    def check_running_task(self, task_name):
        current_tasks = db().query(Task).filter_by(
            name=task_name
        )
        for task in current_tasks:
            if task.status == "running":
                raise errors.TaskAlreadyRunning()
            elif task.status in ("ready", "error"):
                db().delete(task)
                db().commit()

    def serialize_network_cfg(self, cluster):
        serializer = {'nova_network': NovaNetworkConfigurationSerializer,
                      'neutron': NeutronNetworkConfigurationSerializer}
        return serializer[cluster.net_provider].serialize_for_cluster(
            cluster,
            allocate_vips=True
        )


class DeploymentCheckMixin(object):

    # A list of tasks which prevent to start new deploy process
    deployment_tasks = (
        consts.TASK_NAMES.deploy,
        consts.TASK_NAMES.deployment,
        consts.TASK_NAMES.provision,
        consts.TASK_NAMES.stop_deployment,
        consts.TASK_NAMES.reset_environment,
        # NOTE(eli): Node deletion may require nodes redeployment
        # so it's required to preventing parallel deployment
        consts.TASK_NAMES.node_deletion)

    @classmethod
    def check_no_running_deployment(cls, cluster):
        tasks_q = objects.TaskCollection.get_by_name_and_cluster(
            cluster, cls.deployment_tasks).filter_by(
                status=consts.TASK_STATUSES.running)

        tasks_exists = db.query(tasks_q.exists()).scalar()
        if tasks_exists:
            raise errors.DeploymentAlreadyStarted(
                'Cannot perform the actions because there are '
                'running tasks {0}'.format(tasks_q.all()))


class ApplyChangesTaskManager(TaskManager, DeploymentCheckMixin):

    deployment_type = consts.TASK_NAMES.deploy

    def _remove_obsolete_tasks(self):
        current_tasks = objects.TaskCollection.get_cluster_tasks(
            cluster_id=self.cluster.id, names=(consts.TASK_NAMES.deploy,))

        # locking cluster
        objects.Cluster.get_by_uid(
            self.cluster.id,
            fail_if_not_found=True,
            lock_for_update=True
        )

        for task in current_tasks:
            if task.status in (consts.TASK_STATUSES.ready,
                               consts.TASK_STATUSES.error):
                db().delete(task)
        db().flush()

        obsolete_tasks = objects.TaskCollection.filter_by_list(
            current_tasks,
            'name',
            (consts.TASK_NAMES.stop_deployment,
             consts.TASK_NAMES.reset_environment)
        )
        for task in obsolete_tasks:
            db().delete(task)
        db().flush()

    def execute(self, nodes_to_provision_deploy=None, deployment_tasks=None,
                force=False):
        logger.info(
            u"Trying to start deployment at cluster '{0}'".format(
                self.cluster.name or self.cluster.id
            )
        )

        self.check_no_running_deployment(self.cluster)
        self._remove_obsolete_tasks()

        supertask = Task(name=self.deployment_type, cluster=self.cluster,
                         status=consts.TASK_STATUSES.pending)
        db().add(supertask)

        nodes_to_delete = TaskHelper.nodes_to_delete(self.cluster)
        nodes_to_deploy = nodes_to_provision_deploy or \
            TaskHelper.nodes_to_deploy(self.cluster, force)
        nodes_to_provision = TaskHelper.nodes_to_provision(self.cluster)

        if not any([nodes_to_provision, nodes_to_deploy, nodes_to_delete]):
            db().rollback()
            raise errors.WrongNodeStatus("No changes to deploy")

        db().flush()
        TaskHelper.create_action_log(supertask)

        # we should have task committed for processing in other threads
        db().commit()
        nodes_ids_to_deploy = ([node.id for node in nodes_to_provision_deploy]
                               if nodes_to_provision_deploy else None)
        mule.call_task_manager_async(
            self.__class__,
            '_execute_async',
            self.cluster.id,
            supertask.id,
            nodes_to_provision_deploy=nodes_ids_to_deploy,
            deployment_tasks=deployment_tasks,
            force=force
        )

        return supertask

    def _execute_async(self, supertask_id, deployment_tasks=None,
                       nodes_to_provision_deploy=None, force=False):
        """Function for execute task in the mule

        :param supertask_id: id of parent task
        """
        logger.info(u"ApplyChangesTask: execute async starting for task %s",
                    supertask_id)

        supertask = objects.Task.get_by_uid(supertask_id)

        try:
            self._execute_async_content(
                supertask,
                deployment_tasks=deployment_tasks,
                nodes_to_provision_deploy=nodes_to_provision_deploy,
                force=force)
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

    def delete_nodes(self, supertask, nodes_to_delete):
        objects.NodeCollection.lock_nodes(nodes_to_delete)
        # For more accurate progress calculation
        task_weight = 0.4
        task_deletion = supertask.create_subtask(
            consts.TASK_NAMES.node_deletion,
            weight=task_weight)
        logger.debug("Launching deletion task: %s", task_deletion.uuid)
        # we should have task committed for processing in other threads
        db().commit()
        return task_deletion

    def _execute_async_content(self, supertask, deployment_tasks=None,
                               nodes_to_provision_deploy=None, force=False):
        """Processes supertask async in mule

        :param supertask: SqlAlchemy task object
        """

        nodes_to_delete = []
        affected_nodes = []

        if nodes_to_provision_deploy:
            nodes_to_deploy = objects.NodeCollection.get_by_ids(
                nodes_to_provision_deploy)
            nodes_to_provision = filter(lambda n: any([
                n.pending_addition,
                n.needs_reprovision]),
                nodes_to_deploy)
        else:
            nodes_to_deploy = TaskHelper.nodes_to_deploy(self.cluster, force)
            nodes_to_provision = TaskHelper.nodes_to_provision(self.cluster)
            nodes_to_delete = TaskHelper.nodes_to_delete(self.cluster)

        objects.Cluster.adjust_nodes_lists_on_controller_removing(
            self.cluster, nodes_to_delete, nodes_to_deploy)

        task_messages = []
        # Run validation if user didn't redefine
        # provisioning and deployment information

        if not (nodes_to_provision_deploy or
                objects.Cluster.get_provisioning_info(self.cluster) or
                objects.Cluster.get_deployment_info(self.cluster)):
            try:
                self.check_before_deployment(supertask)
            except errors.CheckBeforeDeploymentError:
                db().commit()
                return

        if self.cluster.status == consts.CLUSTER_STATUSES.operational:
            # rerun particular tasks on all deployed nodes
            modified_node_ids = {n.id for n in nodes_to_deploy}
            modified_node_ids.update(n.id for n in nodes_to_provision)
            modified_node_ids.update(n.id for n in nodes_to_delete)
            affected_nodes = objects.Cluster.get_nodes_by_status(
                self.cluster,
                status=consts.NODE_STATUSES.ready,
                exclude=modified_node_ids
            ).all()

        task_deletion, task_provision, task_deployment = None, None, None

        if nodes_to_delete:
            task_deletion = self.delete_nodes(supertask, nodes_to_delete)

        if nodes_to_provision:
            logger.debug("There are nodes to provision: %s",
                         " ".join([objects.Node.get_node_fqdn(n)
                                   for n in nodes_to_provision]))

            # For more accurate progress calculation
            task_weight = 0.4
            task_provision = supertask.create_subtask(
                consts.TASK_NAMES.provision,
                status=consts.TASK_STATUSES.pending,
                weight=task_weight)

            # we should have task committed for processing in other threads
            db().commit()
            provision_message = self._call_silently(
                task_provision,
                tasks.ProvisionTask,
                nodes_to_provision,
                method_name='message'
            )
            db().commit()

            task_provision = objects.Task.get_by_uid(
                task_provision.id,
                fail_if_not_found=True,
                lock_for_update=True
            )
            # if failed to generate task message for orchestrator
            # then task is already set to error
            if task_provision.status == consts.TASK_STATUSES.error:
                return

            task_provision.cache = provision_message
            db().commit()
            task_messages.append(provision_message)

        deployment_message = None
        if nodes_to_deploy or affected_nodes:
            if nodes_to_deploy:
                logger.debug("There are nodes to deploy: %s",
                             " ".join((objects.Node.get_node_fqdn(n)
                                       for n in nodes_to_deploy)))
            if affected_nodes:
                logger.debug("There are nodes affected by deployment: %s",
                             " ".join((objects.Node.get_node_fqdn(n)
                                       for n in affected_nodes)))

            task_deployment = supertask.create_subtask(
                name=consts.TASK_NAMES.deployment,
                status=consts.TASK_STATUSES.pending
            )

            # we should have task committed for processing in other threads
            db().commit()
            deployment_message = self._call_silently(
                task_deployment,
                tasks.DeploymentTask,
                nodes_to_deploy,
                affected_nodes=affected_nodes,
                deployment_tasks=deployment_tasks,
                method_name='message',
                reexecutable_filter=consts.TASKS_TO_RERUN_ON_DEPLOY_CHANGES
            )

            db().commit()
            task_deployment = objects.Task.get_by_uid(
                task_deployment.id,
                fail_if_not_found=True,
                lock_for_update=True
            )
            # if failed to generate task message for orchestrator
            # then task is already set to error
            if task_deployment.status == consts.TASK_STATUSES.error:
                return

            task_deployment.cache = deployment_message
            db().commit()

        if deployment_message:
            task_messages.append(deployment_message)

        # Even if we don't have nodes to deploy, the deployment task
        # should be created. Why? Because we need to update both
        # nodes.yaml and /etc/hosts on all slaves. Since we need only
        # those two tasks, let's create stripped version of
        # deployment.
        if nodes_to_delete and not nodes_to_deploy:
            logger.debug(
                "No nodes to deploy, just update nodes.yaml everywhere.")

            task_deployment = supertask.create_subtask(
                name=consts.TASK_NAMES.deployment,
                status=consts.TASK_STATUSES.pending
            )
            task_message = tasks.UpdateNodesInfoTask.message(task_deployment)
            task_deployment.cache = task_message
            task_messages.append(task_message)
            db().commit()

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

        # We have to execute node deletion task only when provision,
        # deployment and other tasks are in the database. Otherwise,
        # it may be executed too quick (e.g. our tests) and this
        # will affect parent task calculation - it will be marked
        # as 'ready' because by that time it have only two subtasks
        # - network_check and node_deletion - and they're  ready.
        # In order to avoid that wrong behavior, let's send
        # deletion task to execution only when others subtasks in
        # the database.
        if task_deletion:
            self._call_silently(
                task_deletion,
                tasks.DeletionTask,
                tasks.DeletionTask.get_task_nodes_for_cluster(self.cluster),
                check_ceph=True)
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
        try:
            # if there are VIPs with same names in the network configuration
            # the error will be raised. Such situation may occur when, for
            # example, enabled plugins contain conflicting network
            # configuration
            network_info = self.serialize_network_cfg(self.cluster)
        except (errors.DuplicatedVIPNames, errors.NetworkRoleConflict) as e:
            raise errors.CheckBeforeDeploymentError(e.message)

        logger.info(
            u"Network info:\n{0}".format(
                jsonutils.dumps(network_info, indent=4)
            )
        )

        # checking admin intersection with untagged
        network_info["networks"] = [
            n for n in network_info["networks"] if n["name"] != "fuelweb_admin"
        ]

        check_networks = supertask.create_subtask(
            consts.TASK_NAMES.check_networks)

        self._call_silently(
            check_networks,
            tasks.CheckNetworksTask,
            data=network_info,
            check_all_parameters=True
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


class ApplyChangesForceTaskManager(ApplyChangesTaskManager):

    def execute(self, **kwargs):
        kwargs['force'] = True
        return super(ApplyChangesForceTaskManager, self).execute(**kwargs)


class SpawnVMsTaskManager(ApplyChangesTaskManager):

    deployment_type = consts.TASK_NAMES.spawn_vms

    def delete_nodes(self, supertask, nodes_to_delete):
        return None


class ProvisioningTaskManager(TaskManager):

    def execute(self, nodes_to_provision):
        """Run provisioning task on specified nodes."""
        # locking nodes
        nodes_ids = [node.id for node in nodes_to_provision]
        nodes = objects.NodeCollection.filter_by_list(
            None,
            'id',
            nodes_ids,
            order_by='id'
        )

        logger.debug('Nodes to provision: {0}'.format(
            ' '.join([objects.Node.get_node_fqdn(n)
                      for n in nodes_to_provision])))

        task_provision = Task(name=consts.TASK_NAMES.provision,
                              status=consts.TASK_STATUSES.pending,
                              cluster=self.cluster)
        db().add(task_provision)

        for node in nodes:
            objects.Node.reset_vms_created_state(node)

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

        logger.debug('Nodes to deploy: {0}'.format(
            ' '.join([objects.Node.get_node_fqdn(n)
                      for n in nodes_to_deployment])))
        task_deployment = Task(
            name=consts.TASK_NAMES.deployment, cluster=self.cluster,
            status=consts.TASK_STATUSES.pending
        )
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
        stop_running = objects.TaskCollection.filter_by(
            None,
            cluster_id=self.cluster.id,
            name=consts.TASK_NAMES.stop_deployment
        )
        stop_running = objects.TaskCollection.order_by(
            stop_running, 'id'
        ).first()

        if stop_running:
            if stop_running.status in (
                    consts.TASK_STATUSES.running,
                    consts.TASK_STATUSES.pending):
                raise errors.StopAlreadyRunning(
                    "Stopping deployment task "
                    "is already launched"
                )
            else:
                db().delete(stop_running)
                db().commit()

        deployment_task = objects.TaskCollection.filter_by(
            None,
            cluster_id=self.cluster.id,
            name=consts.TASK_NAMES.deployment,
        )
        deployment_task = deployment_task.filter(
            Task.status != consts.TASK_STATUSES.pending
        )
        deployment_task = objects.TaskCollection.order_by(
            deployment_task, '-id'
        ).first()

        provisioning_task = objects.TaskCollection.filter_by(
            None,
            cluster_id=self.cluster.id,
            name=consts.TASK_NAMES.provision,
        )
        provisioning_task = provisioning_task.filter(
            Task.status != consts.TASK_STATUSES.pending
        )
        provisioning_task = objects.TaskCollection.order_by(
            provisioning_task, '-id'
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
            db().commit()

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

        # FIXME(aroma): remove updating of 'deployed_before'
        # when stop action is reworked. 'deployed_before'
        # flag identifies whether stop action is allowed for the
        # cluster. Please, refer to [1] for more details.
        # [1]: https://bugs.launchpad.net/fuel/+bug/1529691
        objects.Cluster.set_deployed_before_flag(self.cluster, value=False)

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

        nodes = objects.Cluster.get_nodes_by_role(
            self.cluster, consts.VIRTUAL_NODE_TYPES.virt)
        for node in nodes:
            objects.Node.reset_vms_created_state(node)

        db().commit()

        supertask = Task(
            name=consts.TASK_NAMES.reset_environment,
            cluster=self.cluster
        )
        db().add(supertask)
        al = TaskHelper.create_action_log(supertask)

        remove_keys_task = supertask.create_subtask(
            consts.TASK_NAMES.reset_environment
        )

        remove_ironic_bootstrap_task = supertask.create_subtask(
            consts.TASK_NAMES.reset_environment
        )

        db.commit()

        rpc.cast('naily', [
            tasks.ResetEnvironmentTask.message(supertask),
            tasks.RemoveIronicBootstrap.message(remove_ironic_bootstrap_task),
            tasks.RemoveClusterKeys.message(remove_keys_task)
        ])
        TaskHelper.update_action_log(supertask, al)
        return supertask


class CheckNetworksTaskManager(TaskManager):

    def execute(self, data, check_all_parameters=False):
        # Make a copy of original 'data' due to being changed by
        # 'tasks.CheckNetworksTask'
        data_copy = copy.deepcopy(data)
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
            data_copy,
            check_all_parameters
        )

        task = objects.Task.get_by_uid(
            task.id,
            fail_if_not_found=True,
            lock_for_update=True
        )
        if task.status == consts.TASK_STATUSES.running:
            # update task status with given data
            objects.Task.update(
                task,
                {'status': consts.TASK_STATUSES.ready, 'progress': 100})
        db().commit()
        return task


class VerifyNetworksTaskManager(TaskManager):

    _blocking_statuses = (
        consts.CLUSTER_STATUSES.deployment,
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
            check_all_parameters=True
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

            # we have remote connectivity checks since fuel 6.1,
            # so we should not create those tasks for old envs
            if StrictVersion(self.cluster.release.environment_version) >= \
                    StrictVersion(consts.FUEL_REMOTE_REPOS):

                # repo connectivity check via default gateway
                repo_check_task = objects.task.Task.create_subtask(
                    task, name=consts.TASK_NAMES.check_repo_availability)
                verify_task.add_subtask(
                    tasks.CheckRepoAvailability(repo_check_task, vlan_ids))

                # repo connectivity check via external gateway
                conf, errors = tasks.CheckRepoAvailabilityWithSetup.get_config(
                    self.cluster)
                # if there is no conf - there is no nodes on which
                # we need to setup network
                if conf:
                    repo_check_task = objects.task.Task.create_subtask(
                        task,
                        consts.TASK_NAMES.check_repo_availability_with_setup)
                    verify_task.add_subtask(
                        tasks.CheckRepoAvailabilityWithSetup(
                            repo_check_task, conf))

                if errors:
                    notifier.notify(
                        "warning",
                        '\n'.join(errors),
                        self.cluster.id
                    )

            db().commit()
            self._call_silently(task, verify_task)

        return task


class ClusterDeletionManager(TaskManager):

    def execute(self):
        current_tasks = objects.TaskCollection.get_cluster_tasks(
            self.cluster.id, names=(consts.TASK_NAMES.cluster_deletion,)
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
        for task in current_tasks:
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


class NodeDeletionTaskManager(TaskManager, DeploymentCheckMixin):

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
            raise errors.InvalidData(
                "Invalid data -- nodes' cluster_ids {0} do not match "
                "cluster's id {1}".format(
                    [node.id for node in invalid_nodes], cluster_id)
            )

    def execute(self, nodes_to_delete, mclient_remove=True):
        cluster = None
        if hasattr(self, 'cluster'):
            cluster = self.cluster

        logger.info("Trying to execute node deletion task with nodes %s",
                    ', '.join(str(node.id) for node in nodes_to_delete))

        self.verify_nodes_with_cluster(nodes_to_delete)
        objects.NodeCollection.lock_nodes(nodes_to_delete)

        if cluster is None:
            # DeletionTask operates on cluster's nodes.
            # Nodes that are not in cluster are simply deleted.

            objects.NodeCollection.delete_by_ids([
                n.id for n in nodes_to_delete])
            db().flush()

            task = Task(name=consts.TASK_NAMES.node_deletion,
                        progress=100,
                        status=consts.TASK_STATUSES.ready)
            db().add(task)
            db().flush()

            return task

        self.check_no_running_deployment(self.cluster)

        task = Task(name=consts.TASK_NAMES.node_deletion,
                    cluster=self.cluster)
        db().add(task)
        for node in nodes_to_delete:
            objects.Node.update(node,
                                {'status': consts.NODE_STATUSES.removing,
                                 'pending_deletion': True})
        db().flush()

        nodes_to_deploy = []
        objects.Cluster.adjust_nodes_lists_on_controller_removing(
            self.cluster, nodes_to_delete, nodes_to_deploy)

        # NOTE(aroma): in case of removing of a controller node we do
        # implicit redeployment of all left controllers here in
        # order to preserve consistency of a HA cluster.
        # The reason following filtering is added is that we must
        # redeploy only controllers in ready status. Also in case
        # one of the nodes is in error state we must cancel the whole
        # operation as result of the redeployment in this case is unpredictable
        # and user may end up with not working cluster
        controllers_with_ready_status = []
        for controller in nodes_to_deploy:
            if controller.status == consts.NODE_STATUSES.error:
                raise errors.ControllerInErrorState()
            elif controller.status == consts.NODE_STATUSES.ready:
                controllers_with_ready_status.append(controller)

        if controllers_with_ready_status:
            logger.debug("There are nodes to deploy: %s",
                         " ".join([objects.Node.get_node_fqdn(n)
                                   for n in controllers_with_ready_status]))
            task_deployment = task.create_subtask(
                consts.TASK_NAMES.deployment)

            deployment_message = self._call_silently(
                task_deployment,
                tasks.DeploymentTask,
                controllers_with_ready_status,
                method_name='message'
            )
            db().flush()

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


class BaseStatsUserTaskManager(TaskManager):

    task_name = None

    task_cls = None

    def execute(self):
        logger.info("Trying to execute %s in the operational "
                    "environments", self.task_name)
        created_tasks = []
        clusters = objects.ClusterCollection.filter_by(
            None, status=consts.CLUSTER_STATUSES.operational)

        for cluster in clusters:
            logger.debug("Creating task for %s on the "
                         "cluster %s", self.task_name, cluster.id)

            primary_controller = objects.Cluster.get_primary_node(
                cluster, 'controller')
            if primary_controller is not None:
                logger.debug("Primary controller cluster %s found: %s. "
                             "Creating task for %s", cluster.id,
                             primary_controller.id, self.task_name)

                if objects.TaskCollection.filter_by(
                        None,
                        cluster_id=cluster.id,
                        name=self.task_name,
                        status=consts.TASK_STATUSES.running).count():
                    logger.debug("Task %s is already running for cluster %s",
                                 self.task_name, cluster.id)
                    continue

                task = Task(name=self.task_name, cluster_id=cluster.id)
                db().add(task)
                db().commit()
                created_tasks.append(task)

                self._call_silently(
                    task,
                    self.task_cls,
                    primary_controller
                )
            else:
                logger.debug("Primary controller not found for cluster %s",
                             cluster.id)
        return created_tasks


class CreateStatsUserTaskManager(BaseStatsUserTaskManager):

    task_name = consts.TASK_NAMES.create_stats_user

    task_cls = tasks.CreateStatsUserTask


class RemoveStatsUserTaskManager(BaseStatsUserTaskManager):

    task_name = consts.TASK_NAMES.remove_stats_user

    task_cls = tasks.RemoveStatsUserTask


class UpdateDnsmasqTaskManager(TaskManager):

    def execute(self):
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


class OpenstackConfigTaskManager(TaskManager):

    def execute(self, filters):
        self.check_running_task(consts.TASK_NAMES.deployment)

        task = Task(name=consts.TASK_NAMES.deployment,
                    cluster=self.cluster,
                    status=consts.TASK_STATUSES.pending)
        db().add(task)

        nodes_to_update = objects.Cluster.get_nodes_to_update_config(
            self.cluster, filters.get('node_id'), filters.get('node_role'))

        message = self._call_silently(
            task, tasks.UpdateOpenstackConfigTask,
            self.cluster, nodes_to_update, method_name='message')

        # locking task
        task = objects.Task.get_by_uid(
            task.id,
            fail_if_not_found=True,
            lock_for_update=True
        )

        if task.is_completed():
            return task

        # locking nodes
        objects.NodeCollection.lock_nodes(nodes_to_update)

        task.cache = copy.copy(message)
        task.cache['nodes'] = [n.id for n in nodes_to_update]

        for node in nodes_to_update:
            node.status = consts.NODE_STATUSES.deploying
            node.progress = 0

        db().commit()

        rpc.cast('naily', message)

        return task
