# -*- coding: utf-8 -*-

#    Copyright 2015 Mirantis, Inc.
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
from nailgun.expression import Expression
from nailgun.logger import logger
from nailgun import objects
from nailgun.orchestrator import tasks_templates as templates
from nailgun.settings import settings


def get_uids_for_tasks(nodes, tasks):
    """Return node uids where particular tasks should be executed

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
                'Wrong roles format, `roles` should be a list or "*" in %s',
                task)
    return get_uids_for_roles(nodes, roles)


def get_uids_for_roles(nodes, roles):
    """Returns list of uids for nodes that matches roles

    :param nodes: list of nodes
    :param roles: list of roles or consts.ALL_ROLES
    :returns: list of strings
    """

    uids = set()

    if roles == consts.ALL_ROLES:
        uids.update([n.uid for n in nodes])
    elif isinstance(roles, list):
        for node in nodes:
            if set(roles) & set(objects.Node.all_roles(node)):
                uids.add(node.uid)
    else:
        logger.warn(
            'Wrong roles format, `roles` should be a list or "*": %s',
            roles)

    return list(uids)


@six.add_metaclass(abc.ABCMeta)
class DeploymentHook(object):

    def should_execute(self):
        """Should be used to define conditions when task should be executed."""

        return True

    @abc.abstractmethod
    def serialize(self):
        """Serialize task in expected by orchestrator format.

        This interface should return generator, because in some cases one
        external task - should serialize several tasks internally.
        """


class ExpressionBasedTask(DeploymentHook):

    def __init__(self, task, cluster):
        self.task = task
        self.cluster = cluster

    @property
    def _expression_context(self):
        return {'cluster': self.cluster,
                'settings': self.cluster.attributes.editable}

    def should_execute(self):
        if 'condition' not in self.task:
            return True
        return Expression(
            self.task['condition'], self._expression_context).evaluate()


class GenericNodeHook(ExpressionBasedTask):
    """Should be used for node serialization.
    """

    hook_type = abc.abstractproperty

    def __init__(self, task, cluster, node):
        self.node = node
        super(GenericNodeHook, self).__init__(task, cluster)


class PuppetHook(GenericNodeHook):

    hook_type = 'puppet'

    def serialize(self):
        yield templates.make_puppet_task([self.node['uid']], self.task)


class StandartConfigRolesHook(ExpressionBasedTask):
    """Role hooks that serializes task based on config file only."""

    def __init__(self, task, cluster, nodes):
        self.nodes = nodes
        super(StandartConfigRolesHook, self).__init__(task, cluster)

    def get_uids(self):
        return get_uids_for_roles(self.nodes, self.task['role'])

    def serialize(self):
        uids = self.get_uids()
        if uids:
            yield templates.make_generic_task(uids, self.task)


class GenericRolesHook(StandartConfigRolesHook):

    identity = abc.abstractproperty


class UploadMOSRepo(GenericRolesHook):

    identity = 'upload_core_repos'

    def get_uids(self):
        return get_uids_for_roles(self.nodes, consts.ALL_ROLES)

    def make_repo_url(self, repo_mask, context):
        return repo_mask.format(**context)

    def serialize(self):
        uids = self.get_uids()
        operating_system = self.cluster.release.operating_system
        repo_metadata = self.cluster.release.orchestrator_data.repo_metadata
        repo_name = 'nailgun'

        context = {
            'MASTER_IP': settings.MASTER_IP,
            'OPENSTACK_VERSION': self.cluster.release.version}

        # repo_metadata stores its values by key of release
        for release, repo_url_mask in six.iteritems(repo_metadata):
            repo_url = self.make_repo_url(repo_url_mask, context)
            if operating_system == consts.RELEASE_OS.centos:
                yield templates.make_centos_repo_task(
                    repo_name, repo_url, uids)
            elif operating_system == consts.RELEASE_OS.ubuntu:
                yield templates.make_versioned_ubuntu(
                    repo_name, repo_url, uids)

        if operating_system == consts.RELEASE_OS.centos:
            yield templates.make_yum_clean(uids)
        elif operating_system == consts.RELEASE_OS.ubuntu:
            yield templates.make_apt_update_task(uids)


class RsyncPuppet(GenericRolesHook):

    identity = 'rsync_core_puppet'

    def get_uids(self):
        return get_uids_for_roles(self.nodes, consts.ALL_ROLES)

    def serialize(self):
        src_path = self.task['parameters']['src'].format(
            MASTER_IP=settings.MASTER_IP,
            OPENSTACK_VERSION=self.cluster.release.version)
        uids = self.get_uids()
        yield templates.make_sync_scripts_task(
            uids, src_path, self.task['parameters']['dst'])


class RestartRadosGW(GenericRolesHook):

    identity = 'restart_radosgw'

    def should_execute(self):
        for node in self.nodes:
            if 'ceph-osd' in node.all_roles:
                return True
        return False


class TaskSerializers(object):
    """Class serves as fabric for different types of task serializers."""

    stage_serializers = [UploadMOSRepo, RsyncPuppet, RestartRadosGW]
    deploy_serializers = [PuppetHook]

    def __init__(self, stage_serializers=None, deploy_serializers=None):
        """Task serializers for stage (pre/post) are different from
        serializers used for main deployment.

        This should be considered as limitation of current architecture,
        and will be solved in next releases.

        :param stage_serializers: list of GenericRoleHook classes
        :param deploy_serializers: list of GenericNodeHook classes
        """
        self._stage_serializers_map = {}
        self._deploy_serializers_map = {}

        if stage_serializers is None:
            stage_serializers = self.stage_serializers
        for serializer in stage_serializers:
            self.add_stage_serializer(serializer)

        if deploy_serializers is None:
            deploy_serializers = self.deploy_serializers
        for serializer in deploy_serializers:
            self.add_deploy_serializer(serializer)

    def add_stage_serializer(self, serializer):
        self._stage_serializers_map[serializer.identity] = serializer

    def add_deploy_serializer(self, serializer):
        self._deploy_serializers_map[serializer.hook_type] = serializer

    def get_deploy_serializer(self, task):
        if 'type' not in task:
            raise errors.InvalidData('Task %s should have type', task)

        if task['type'] in self._deploy_serializers_map:
            return self._deploy_serializers_map[task['type']]
        else:
            # Currently we are not supporting anything except puppet as main
            # deployment engine, therefore exception should be raised,
            # but it should be verified by validation as well
            raise errors.SerializerNotSupported(
                'Serialization of type {0} not supported. Task {1}'.format(
                    task['type'], task))

    def get_stage_serializer(self, task):
        if 'id' not in task:
            raise errors.InvalidData('Task %s should have id', task)

        if task['id'] in self._stage_serializers_map:
            return self._stage_serializers_map[task['id']]
        else:
            return StandartConfigRolesHook
