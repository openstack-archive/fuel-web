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
from nailgun.errors import errors
from nailgun.logger import logger
from nailgun.orchestrator.deployment_graph import create_graph
import nailgun.orchestrator.priority_serializers as ps
import nailgun.orchestrator.tasks_templates as templates
from nailgun.settings import settings


def get_uids_for_tasks(nodes, tasks):
    """Return uids where particular tasks should be executed

    :param nodes: list of Node db objects
    :param tasks: list of dicts
    :returns: list of strings
    """
    roles = []
    for task in tasks:
        if task['role'] == consts.ALL_ROLES:
            return get_uids_for_roles(nodes, consts.ALL_ROLES)
        elif isinstance(task['role'], list):
            roles.extend(task['role'])
        else:
            logger.warn(
                'Wrong roles format, `roles` should be a list or "*": %s',
                task['role'])
    return get_uids_for_roles(nodes, roles)


def get_uids_for_roles(nodes, roles):
    """Returns list of uids for nodes that matches roles

    :param nodes: list of nodes
    :param roles: list of roles or consts.ALL_ROLES
    :returns: list of strings
    """

    uids = []

    if roles == consts.ALL_ROLES:
        uids.extend([n.uid for n in nodes])
    elif isinstance(roles, list):
        for node in nodes:
            if set(roles) & set(node.all_roles):
                uids.append(node.uid)
    else:
        logger.warn(
            'Wrong roles format, `roles` should be a list or "*": %s',
            roles)

    return list(set(uids))


@six.add_metaclass(abc.ABCMeta)
class DeploymentHook(object):

    def should_execute(self):
        """Should be used to define conditions when task should be executed."""
        return True

    @abc.abstractmethod
    def serialize(self):
        """Serialize task in expected by orchestrator format.
           In case of task can not be serialized - return None
        """


class GenericNodeHook(DeploymentHook):
    """Should be used for node serialization.
    """

    def __init__(self, task, node):
        self.task = task
        self.node = node


class PuppetHook(GenericNodeHook):

    hook_type = 'puppet'

    def serialize(self):
        yield templates.make_puppet_task([self.node['uid']], self.task)


class GenericRolesHook(DeploymentHook):

    def __init__(self, task, cluster, nodes):
        self.task = task
        self.cluster = cluster
        self.nodes = nodes

    def get_uids(self):
        return get_uids_for_roles(self.nodes, self.task['role'])

    def serialize(self):
        uids = self.get_uids()
        yield templates.make_generic_task(uids, self.task)


class UploadMOSRepo(GenericRolesHook):

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


class RsyncPuppet(GenericRolesHook):

    identity = 'rsync_mos_puppet'

    def get_uids(self):
        return get_uids_for_roles(self.nodes, '*')

    def serialize(self):
        path = self.task['parameters']['src'].format(
            OPENSTACK_VERSION=self.cluster.release.version)
        uids = self.get_uids()
        yield templates.make_sync_scripts_task(
            uids, path, self.task['parameters']['dst'])


IDENTITY_BASED = dict((task.identity, task)
                      for task in [UploadMOSRepo, RsyncPuppet])

TYPE_BASED = dict((task.hook_type, task)
                  for task in [PuppetHook])


def pre_tasks_serialize(cluster, nodes):
    #going to remove this in next patchsets
    graph = create_graph(cluster)
    tasks = graph.get_tasks(consts.STAGES.pre_deployment).topology
    serialized = []
    for task in tasks:
        if task['id'] in IDENTITY_BASED:
            serializer = IDENTITY_BASED[task['id']](task, cluster, nodes)
        else:
            serializer = GenericRolesHook(task, cluster, nodes)
        if not serializer.should_execute():
            continue
        for task in serializer.serialize():
            serialized.append(task)
    return serialized


def deploy_task_serialize(graph, node):
    """Serialize tasks with necessary for orchestrator attributes

    :param graph: DeploymentGraph instance with loaded tasks
    :param node: dict with serialized node
    """
    tasks = graph.get_tasks(node['role']).topology
    serialized = []
    priority = ps.Priority()
    for task in tasks:
        if task['type'] in TYPE_BASED:
            serializer = TYPE_BASED[task['type']](task, node)

            if not serializer.should_execute():
                continue
            for item in serializer.serialize():
                item['priority'] = priority.next()
                serialized.append(item)
        else:
            #Currently we are not supporting anything except puppet as main
            #deployment engine, therefore exception should be raised,
            #but it should be verified by validation as well
            raise errors.SerializerNotSupported(
                'Serialization of type {0} not supported. Task {1}'.format(
                    task['type'], task))
    return serialized
