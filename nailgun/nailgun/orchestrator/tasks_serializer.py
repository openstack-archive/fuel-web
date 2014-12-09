# -*- coding: utf-8 -*-

#    Copyright 2014 Mirantis, Inc.
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

import abc
import six

from nailgun import consts
from nailgun.logger import logger
from nailgun import objects
import nailgun.orchestrator.tasks_templates as templates


def get_uids_for_tasks(nodes, tasks):
    """Return uids where particular tasks should be executed

    :param nodes: list of Node db objects
    :param tasks: list of dicts
    :returns: list of strings
    """
    uids = []
    for task in tasks:
        if isinstance(task['role'], list):
            for node in nodes:
                required_for_node = set(task['role']) & set(node.all_roles)
                if required_for_node:
                    uids.append(node.uid)
        elif task['role'] == '*':
            uids.extend([n.uid for n in nodes])
        else:
            logger.warn(
                'Wrong task format, `role` should be a list or "*": %s',
                task)

    return list(set(uids))


def get_uids_for_task(nodes, task):
    """Return uids where particular tasks should be executed

    :param nodes: list of Node db objects
    :param task: dict
    :returns: list of strings
    """
    return get_uids_for_tasks(nodes, [task])


@six.add_metaclass(abc.ABCMeta)
class OrchestratorHook(object):

    def __init__(self, cluster, nodes):
        self.cluster = cluster
        self.nodes = nodes

    def condition(self):
        """Should be used to define conditions when task should be executed."""
        return True

    @abc.abstractmethod
    def serialize(self):
        """Serialize task in expected by orchestrator format.
           In case of task can not be serialized - return None
        """


class UploadGlance(OrchestratorHook):

    def condition(self):
        if self.cluster.status == consts.CLUSTER_STATUSES.operational:
            return False
        return True

    def serialize(self):
        primary_controller = None
        controller = None
        for node in self.nodes:
            roles = objects.Node.all_roles(node)
            if 'primary-controller' in roles:
                primary_controller = node
                break
            elif 'controller' in roles:
                controller = node
                break
        primary_controller = primary_controller or controller
        if not primary_controller:
            return None
        params = {'puppet_manifests': '/etc/puppet/tasks/upload_glance.pp',
                  'puppet_moduels': '/etc/puppet/modules',
                  'timeout': 360}
        task = templates.make_puppet_task(
            [primary_controller.uid],
            {'parameters': params})
        task['fail_on_error'] = True
        return task


class UpdateNoQuorum(OrchestratorHook):

    def condition(self):
        if self.cluster.status == consts.CLUSTER_STATUSES.operational:
            return False
        if not self.cluster.is_ha_mode:
            return False
        return True

    def serialize(self):
        primary_controller = None
        controller = None
        for node in self.nodes:
            roles = objects.Node.all_roles(node)
            if 'primary-controller' in roles:
                primary_controller = node
                break
            elif 'controller' in roles:
                controller = node
                break
        primary_controller = primary_controller or controller
        if not primary_controller:
            return None
        params = {'puppet_manifests': '/etc/puppet/tasks/update_noquorum.pp',
                  'puppet_moduels': '/etc/puppet/modules',
                  'timeout': 360}
        task = templates.make_puppet_task(
            [primary_controller.uid],
            {'parameters': params})
        task['fail_on_error'] = True
        return task


class UpdateClusterHostsInfo(OrchestratorHook):

    def serialize(self):
        #it should be executed for all nodes that was already deployed
        #also we will need updated hosts info somehow
        uids = list(set([n.uid for n in self.cluster.nodes]))
        params = {'puppet_manifests': '/etc/puppet/tasks/update_hosts.pp',
                  'puppet_modules': '/etc/puppet/modules',
                  'timeout': 360}
        task = templates.make_puppet_task(
            uids,
            {'parameters': params})
        task['fail_on_error'] = True
        return task


class SyncPuppet(OrchestratorHook):

    def serialize(self):
        uids = list(set([n.uid for n in self.nodes()]))
        task = templates.make_sync_scripts_task(
            uids, '/etc/puppet/', '/etc/puppet/')
        task['fail_on_error'] = True
        return task


class UpdateTime(OrchestratorHook):

    def serialize(self):
        uids = list(set([n.uid for n in self.nodes]))
        params = {'parameters': {
            'cmd': 'echo 12',
            'timeout': 120
        }}
        task = templates.make_shell_task(uids, params)
        task['fail_on_error'] = True
        return task


class HookSerializer(object):

    tasks = []

    def __init__(self, cluster, nodes):
        self.cluster = cluster
        self.nodes = nodes

    def serialize(self):
        serialized = []
        for task in self.tasks:
            task = task(self.cluster, self.nodes)
            if task.condition():
                serialized_task = task.serialize()
                if serialized_task is not None:
                    serialized.append(serialized_task)
        return serialized


class PostHooksSerializer(HookSerializer):
    """Serialize tasks for post_deployment stage."""

    tasks = [UploadGlance, UpdateNoQuorum]


class PreHooksSerialier(HookSerializer):
    """Serialize tasks for pre_deployment stage."""

    tasks = [UpdateTime, SyncPuppet, UpdateClusterHostsInfo]
