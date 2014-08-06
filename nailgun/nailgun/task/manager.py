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

from nailgun.objects.serializers.network_configuration \
    import NeutronNetworkConfigurationSerializer
from nailgun.objects.serializers.network_configuration \
    import NovaNetworkConfigurationSerializer

from nailgun.consts import CLUSTER_STATUSES
from nailgun.consts import NODE_STATUSES
from nailgun.consts import TASK_NAMES
from nailgun.consts import TASK_STATUSES
from nailgun.db import db
from nailgun.db.sqlalchemy.models import Cluster
from nailgun.db.sqlalchemy.models import Task
from nailgun.errors import errors
from nailgun.logger import logger
from nailgun import objects
from nailgun.openstack.common import jsonutils
import nailgun.rpc as rpc
from nailgun.task import task as tasks
from nailgun.task.task import TaskHelper


class TaskManager(object):

    def __init__(self, cluster_id=None):
        if cluster_id:
            self.cluster = db().query(Cluster).get(cluster_id)

    def _call_silently(self, task, instance, *args, **kwargs):
        method = getattr(instance, kwargs.pop('method_name', 'execute'))
        if task.status == TASK_STATUSES.error:
            return
        try:
            return method(task, *args, **kwargs)
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


class ApplyChangesTaskManager(TaskManager):

    def _lock_required_tasks(self):
        names = (
            TASK_NAMES.deploy,
            TASK_NAMES.stop_deployment,
            TASK_NAMES.reset_environment
        )
        return objects.TaskCollection.lock_cluster_tasks(
            cluster_id=self.cluster.id, names=names
        )

    def _remove_obsolete_tasks(self):
        locked_tasks = self._lock_required_tasks()
        current_tasks = objects.TaskCollection.filter_by(
            locked_tasks,
            name=TASK_NAMES.deploy
        )
        for task in current_tasks:
            if task.status == TASK_STATUSES.running:
                db().commit()
                raise errors.DeploymentAlreadyStarted()
            elif task.status in (TASK_STATUSES.ready, TASK_STATUSES.error):
                db().delete(task)
        db().flush()

        obsolete_tasks = objects.TaskCollection.filter_by_list(
            locked_tasks,
            'name',
            (TASK_NAMES.stop_deployment, TASK_NAMES.reset_environment)
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

        supertask = Task(name=TASK_NAMES.deploy, cluster=self.cluster)
        db().add(supertask)
        # we should have task committed for processing in other threads
        db().commit()

        nodes_to_delete = TaskHelper.nodes_to_delete(self.cluster)
        nodes_to_deploy = TaskHelper.nodes_to_deploy(self.cluster)
        nodes_to_provision = TaskHelper.nodes_to_provision(self.cluster)

        task_messages = []
        if not any([nodes_to_provision, nodes_to_deploy, nodes_to_delete]):
            db().rollback()
            raise errors.WrongNodeStatus("No changes to deploy")

        # Run validation if user didn't redefine
        # provisioning and deployment information

        if (not objects.Cluster.get_provisioning_info(self.cluster) and
                not objects.Cluster.get_deployment_info(self.cluster)):
            try:
                self.check_before_deployment(supertask)
            except errors.CheckBeforeDeploymentError:
                db().commit()
                return supertask

        task_deletion, task_provision, task_deployment = None, None, None

        if nodes_to_delete:
            objects.TaskCollection.lock_cluster_tasks(self.cluster.id)
            # For more accurate progress calculation
            task_weight = 0.4
            task_deletion = supertask.create_subtask(TASK_NAMES.node_deletion,
                                                     weight=task_weight)
            logger.debug("Launching deletion task: %s", task_deletion.uuid)
            # we should have task committed for processing in other threads
            db().commit()
            self._call_silently(task_deletion, tasks.DeletionTask)

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
            task_provision = supertask.create_subtask(TASK_NAMES.provision,
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
            if task_provision.status == TASK_STATUSES.error:
                return supertask

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
            task_deployment = supertask.create_subtask(TASK_NAMES.deployment)
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
            if task_deployment.status == TASK_STATUSES.error:
                return supertask

            task_deployment.cache = deployment_message
            db().commit()
            task_messages.append(deployment_message)

        if nodes_to_provision:
            nodes_to_provision = objects.NodeCollection.lock_nodes(
                nodes_to_provision
            )
            for node in nodes_to_provision:
                node.status = NODE_STATUSES.provisioning
            db().commit()

        objects.Cluster.get_by_uid(
            self.cluster.id,
            fail_if_not_found=True,
            lock_for_update=True
        )
        self.cluster.status = CLUSTER_STATUSES.deployment
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
        return supertask

    def check_before_deployment(self, supertask):
        # checking admin intersection with untagged
        network_info = self.serialize_network_cfg(self.cluster)
        network_info["networks"] = [
            n for n in network_info["networks"] if n["name"] != "fuelweb_admin"
        ]

        check_networks = supertask.create_subtask(TASK_NAMES.check_networks)
        self._call_silently(
            check_networks,
            tasks.CheckNetworksTask,
            data=network_info,
            check_admin_untagged=True
        )
        if check_networks.status == TASK_STATUSES.error:
            logger.warning(
                "Checking networks failed: %s", check_networks.message
            )
            raise errors.CheckBeforeDeploymentError(check_networks.message)
        db().delete(check_networks)
        db().refresh(supertask)
        db().flush()

        # checking prerequisites
        check_before = supertask.create_subtask(
            TASK_NAMES.check_before_deployment
        )
        logger.debug("Checking prerequisites task: %s", check_before.uuid)
        self._call_silently(
            check_before,
            tasks.CheckBeforeDeploymentTask
        )
        # if failed to check prerequisites
        # then task is already set to error
        if check_before.status == TASK_STATUSES.error:
            logger.warning(
                "Checking prerequisites failed: %s", check_before.message
            )
            raise errors.CheckBeforeDeploymentError(check_before.message)
        logger.debug(
            "Checking prerequisites is successful, starting deployment..."
        )
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

        task_provision = Task(name='provision', cluster=self.cluster)
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
            node.status = NODE_STATUSES.provisioning
            node.progress = 0

        db().commit()

        rpc.cast('naily', provision_message)

        return task_provision


class DeploymentTaskManager(TaskManager):

    def execute(self, nodes_to_deployment):
        # locking nodes for update
        objects.NodeCollection.lock_nodes(nodes_to_deployment)
        objects.NodeCollection.update_slave_nodes_fqdn(nodes_to_deployment)

        logger.debug('Nodes to deploy: {0}'.format(
            ' '.join([n.fqdn for n in nodes_to_deployment])))
        task_deployment = Task(name='deployment', cluster=self.cluster)
        db().add(task_deployment)

        deployment_message = self._call_silently(
            task_deployment,
            tasks.DeploymentTask,
            nodes_to_deployment,
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
            TASK_NAMES.stop_deployment,
            TASK_NAMES.deployment,
            TASK_NAMES.provision
        )
        objects.TaskCollection.lock_cluster_tasks(
            self.cluster.id,
            names=names
        )

        stop_running = objects.TaskCollection.filter_by(
            None,
            cluster_id=self.cluster.id,
            name=TASK_NAMES.stop_deployment,
        )
        stop_running = objects.TaskCollection.order_by(
            stop_running, 'id'
        ).first()

        if stop_running:
            if stop_running.status == TASK_STATUSES.running:
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
            name=TASK_NAMES.deployment,
        )
        deployment_task = objects.TaskCollection.order_by(
            deployment_task, 'id'
        ).first()

        provisioning_task = objects.TaskCollection.filter_by(
            None,
            cluster_id=self.cluster.id,
            name=TASK_NAMES.provision,
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

        task = Task(
            name="stop_deployment",
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
            name='deploy',
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
                'deploy',
                'deployment',
                'stop_deployment'
            ])
        )
        for task in obsolete_tasks:
            db().delete(task)
        db().commit()

        task = Task(
            name="reset_environment",
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
                'deploy',
                'deployment',
                'reset_environment',
                'stop_deployment'
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
        task_update = Task(name='update', cluster=self.cluster)
        db().add(task_update)
        self.cluster.status = 'update'
        db().flush()

        deployment_message = self._call_silently(
            task_update,
            tasks.UpdateTask,
            nodes_to_change,
            method_name='message')

        db().refresh(task_update)

        task_update.cache = deployment_message

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
            name=TASK_NAMES.check_networks
        )
        locked_tasks = objects.TaskCollection.order_by(locked_tasks, 'id')
        check_networks = objects.TaskCollection.lock_for_update(
            locked_tasks
        ).first()
        if check_networks:
            db().delete(check_networks)
            db().flush()

        task = Task(
            name=TASK_NAMES.check_networks,
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
        if task.status == TASK_STATUSES.running:
            # update task status with given data
            data = {'status': TASK_STATUSES.ready, 'progress': 100}
            objects.Task.update(task, data)
        db().commit()
        return task


class VerifyNetworksTaskManager(TaskManager):

    def remove_previous_task(self):
        locked_tasks = objects.TaskCollection.filter_by(
            None,
            cluster_id=self.cluster.id
        )
        locked_tasks = objects.TaskCollection.filter_by_list(
            locked_tasks,
            'name',
            (TASK_NAMES.check_networks, TASK_NAMES.verify_networks),
            order_by='id'
        )
        locked_tasks = objects.TaskCollection.lock_for_update(
            locked_tasks
        ).all()

        check_networks = objects.TaskCollection.filter_by(
            locked_tasks,
            name=TASK_NAMES.check_networks
        )
        check_networks = list(check_networks)

        if check_networks:
            db().delete(check_networks[0])
            db().flush()

        verification_tasks = objects.TaskCollection.filter_by(
            locked_tasks,
            name=TASK_NAMES.verify_networks
        )
        verification_tasks = list(verification_tasks)

        if verification_tasks:
            ver_task = verification_tasks[0]
            if ver_task.status == TASK_STATUSES.running:
                raise errors.CantRemoveOldVerificationTask()
            for subtask in ver_task.subtasks:
                db().delete(subtask)
            db().delete(ver_task)
            db().flush()

    def execute(self, nets, vlan_ids):
        self.remove_previous_task()

        task = Task(
            name=TASK_NAMES.check_networks,
            cluster=self.cluster
        )

        if len(self.cluster.nodes) < 2:
            task.status = TASK_STATUSES.error
            task.progress = 100
            task.message = ('At least two nodes are required to be '
                            'in the environment for network verification.')
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

        if task.status != TASK_STATUSES.error:
            # this one is connected with UI issues - we need to
            # separate if error happened inside nailgun or somewhere
            # in the orchestrator, and UI does it by task name.
            task.name = TASK_NAMES.verify_networks
            verify_task = tasks.VerifyNetworksTask(task, vlan_ids)

            if tasks.CheckDhcpTask.enabled(self.cluster):
                dhcp_subtask = objects.task.Task.create_subtask(
                    task, name=TASK_NAMES.check_dhcp)
                verify_task.add_subtask(tasks.CheckDhcpTask(
                    dhcp_subtask, vlan_ids))

            if tasks.MulticastVerificationTask.enabled(self.cluster):
                multicast = objects.task.Task.create_subtask(
                    task, name=TASK_NAMES.multicast_verification)
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
            (TASK_NAMES.cluster_deletion,)
        )

        deploy_running = objects.TaskCollection.filter_by(
            None,
            cluster_id=self.cluster.id,
            name=TASK_NAMES.deploy,
            status=TASK_STATUSES.running
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

        logger.debug("Removing cluster tasks")
        for task in current_cluster_tasks:
            if task.status == TASK_STATUSES.running:
                db().rollback()
                raise errors.DeletionAlreadyStarted()
            elif task.status in (TASK_STATUSES.ready, TASK_STATUSES.error):
                for subtask in task.subtasks:
                    db().delete(subtask)
                db().delete(task)
        db().flush()

        logger.debug("Labeling cluster nodes to delete")
        for node in self.cluster.nodes:
            node.pending_deletion = True
            db().add(node)
        db().flush()

        self.cluster.status = CLUSTER_STATUSES.remove
        db().add(self.cluster)

        logger.debug("Creating cluster deletion task")
        task = Task(name="cluster_deletion", cluster=self.cluster)
        db().add(task)
        db().commit()
        self._call_silently(
            task,
            tasks.ClusterDeletionTask
        )
        return task


class DownloadReleaseTaskManager(TaskManager):

    def __init__(self, release_data):
        self.release_data = release_data

    def execute(self):
        logger.debug("Creating release dowload task")
        task = Task(name="download_release")
        db().add(task)
        db().commit()
        self._call_silently(
            task,
            tasks.DownloadReleaseTask,
            self.release_data
        )
        return task


class DumpTaskManager(TaskManager):

    def execute(self):
        logger.info("Trying to start dump_environment task")
        self.check_running_task('dump')

        task = Task(name="dump")
        db().add(task)
        db().commit()
        self._call_silently(
            task,
            tasks.DumpTask,
        )
        return task


class GenerateCapacityLogTaskManager(TaskManager):

    def execute(self):
        logger.info("Trying to start capacity_log task")
        self.check_running_task('capacity_log')

        task = Task(name='capacity_log')
        db().add(task)
        db().commit()
        self._call_silently(
            task,
            tasks.GenerateCapacityLogTask)
        return task
