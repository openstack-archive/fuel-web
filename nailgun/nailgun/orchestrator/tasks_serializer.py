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
import nailgun.orchestrator.tasks_templates as templates
from nailgun.settings import settings


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


def get_uids_for_roles(nodes, roles):
    """Returns list of uids for nodes that matches roles

    :param nodes: list of nodes
    :param roles: list of roles or *
    """

    uids = []
    if roles == '*':
        uids.extend([n.uid for n in nodes])
    elif isinstance(roles, list):

        for node in nodes:
            required_for_node = set(roles) & set(node.all_roles)
            if required_for_node:
                uids.append(node.uid)

    else:
        logger.warn(
            'Wrong roles format, `roles` should be a list or "*": %s',
            roles)

    return list(set(uids))


@six.add_metaclass(abc.ABCMeta)
class OrchestratorHook(object):

    def __init__(self, task, cluster, nodes):
        self.task = task
        self.cluster = cluster
        self.nodes = nodes

    def condition(self):
        """Should be used to define conditions when task should be executed."""
        return True

    def get_uids(self):
        return get_uids_for_roles(self.nodes, self.task['role'])

    @abc.abstractmethod
    def serialize(self):
        """Serialize task in expected by orchestrator format.
           In case of task can not be serialized - return None
        """


class GenericRolesHook(OrchestratorHook):

    def serialize(self):
        uids = self.get_uids()
        return templates.make_generic_task(uids, self.task)


class UploadMOSRepo(OrchestratorHook):

    identity = 'upload_mos_repos'

    def get_uids(self):
        return get_uids_for_roles(self.nodes, '*')

    def make_repo_url(self, repo_mask, context):
        return repo_mask.format(**context)

    def serialize(self):
        uids = self.get_uids()
        operating_system = self.cluster.release.operating_system
        repo_metadata = self.cluster.release.orchestrator_data.repo_metadata
        #repo_metadata stores its values by key of release

        context = {
            'MASTER_IP': settings.MASTER_IP,
            'OPENSTACK_VERSION': self.cluster.release.version}

        for key, value in six.iteritems(repo_metadata):
            repo_url = self.make_repo_url(value, context)
            if operating_system == consts.RELEASE_OS.centos:
                yield templates.make_centos_repo_task(
                    'nailgun', repo_url, uids)
            elif operating_system == consts.RELEASE_OS.ubuntu:
                yield templates.make_ubuntu_repo_task(
                    'nailgun', repo_url, uids)

        if operating_system == consts.RELEASE_OS.centos:
            yield templates.make_yum_clean(uids)
        elif operating_system == consts.RELEASE_OS.ubuntu:
            yield templates.make_apt_update_task(uids)


class RsyncPuppet(OrchestratorHook):

    identity = 'rsync_mos_puppet'

    def get_uids(self):
        return get_uids_for_roles(self.nodes, '*')

    def serialize(self):
        path = self.task['parameters']['src'].format(
            OPENSTACK_VERSION=self.cluster.release.version)
        uids = self.get_uids()
        yield templates.make_sync_scripts_task(
            uids, path, self.task['parameters']['dst'])


PRE_STAGE_TASKS = [UploadMOSRepo, RsyncPuppet]


def pre_tasks_serialize(tasks, cluster, nodes):
    tasks_serializer = dict((task.identity, task) for task in PRE_STAGE_TASKS)
    serialized = []
    for task in tasks:
        if task['id'] in tasks_serializer:
            serializer = tasks_serializer[task['id']](task, cluster, nodes)
        else:
            serializer = GenericRolesHook(task, cluster, nodes)
        for task in serializer.serialize():
            serialized.append(task)
    return serialized
