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

import os
from string import Formatter

import abc
import six
import yaml

from nailgun import consts
from nailgun.errors import errors
from nailgun.expression import Expression
from nailgun.logger import logger
from nailgun import objects
from nailgun.orchestrator import deployment_serializers
from nailgun.orchestrator import tasks_templates as templates
from nailgun.settings import settings


class TemplateFormatter(Formatter):

    def get_value(self, field_name, args, kwds):
        try:
            v = Formatter.get_value(self, field_name, args, kwds)
        except KeyError:
            return ''
        return v


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
        elif task['role'] == consts.MASTER_ROLE:
            return ['master']
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
    elif roles == consts.MASTER_ROLE:
        return ['master']
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

    @abc.abstractmethod
    def serialize(self):
        """Serialize task in expected by orchestrator format.

        This interface should return generator, because in some cases one
        external task - should serialize several tasks internally.
        """


class ExpressionBasedTask(DeploymentHook):

    def __init__(self, task, cluster, node):
        self.task = task
        self.cluster = cluster
        self.nodes = node

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


class PuppetHook(GenericNodeHook):

    hook_type = 'puppet'

    def serialize(self):
        yield templates.make_puppet_task([self.nodes['uid']], self.task)


class StandartConfigRolesHook(ExpressionBasedTask):
    """Role hooks that serializes task based on config file only."""

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

    def serialize(self):
        uids = self.get_uids()
        operating_system = self.cluster.release.operating_system
        repos = objects.Attributes.merged_attrs_values(
            self.cluster.attributes)['repo_setup']['repos']

        if operating_system == consts.RELEASE_OS.centos:
            for repo in repos:
                yield templates.make_centos_repo_task(uids, repo)
            yield templates.make_yum_clean(uids)
        elif operating_system == consts.RELEASE_OS.ubuntu:
            # NOTE(ikalnitsky):
            # We have to clear /etc/apt/sources.list, because it
            # has a lot of invalid repos right after provisioning
            # and that lead us to deployment failures.
            yield templates.make_shell_task(uids, {
                'parameters': {
                    'cmd': '> /etc/apt/sources.list',
                    'timeout': 10
                }})
            yield templates.make_ubuntu_apt_disable_ipv6(uids)
            # NOTE(kozhukalov):
            # This task is to allow installing packages from
            # unauthenticated repositories.
            yield templates.make_ubuntu_unauth_repos_task(uids)
            for repo in repos:
                yield templates.make_ubuntu_sources_task(uids, repo)

                if repo.get('priority'):
                    # do not add preferences task to task list if we can't
                    # complete it (e.g. can't retrieve or parse Release file)
                    task = templates.make_ubuntu_preferences_task(uids, repo)
                    if task is not None:
                        yield task
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


class GenerateKeys(GenericRolesHook):

    identity = 'generate_keys'

    def serialize(self):
        uids = self.get_uids()
        self.task['parameters']['cmd'] = self.task['parameters']['cmd'].format(
            CLUSTER_ID=self.cluster.id)
        yield templates.make_shell_task(uids, self.task)


class CopyKeys(GenericRolesHook):

    identity = 'copy_keys'

    def serialize(self):
        for file_path in self.task['parameters']['files']:
            file_path['src'] = file_path['src'].format(
                CLUSTER_ID=self.cluster.id)
        uids = self.get_uids()
        yield templates.make_generic_task(
            uids, self.task)


class RestartRadosGW(GenericRolesHook):

    identity = 'restart_radosgw'

    def should_execute(self):
        for node in self.nodes:
            if 'ceph-osd' in node.all_roles:
                return True
        return False


class BaseVMSHook(GenericRolesHook):

    def should_execute(self):
        return bool(objects.VirtualMachinesRequestsCollection.
                    get_spawning_computes(self.cluster.id))

    def get_uids(self):
        return objects.VirtualMachinesRequestsCollection.\
            get_spawning_computes(self.cluster.id)


class UploadVMSInfo(BaseVMSHook):
    """Hook that uploads info about all nodes in cluster."""

    identity = 'upload_vms_info'

    def serialize(self):
        uids = self.get_uids()
        template_path = self.task['parameters']['template_path']
        nodes = []
        template = open(template_path).read()
        for uid in uids:
            node = {'uid': uid}
            vms = objects.VirtualMachinesRequestsCollection.\
                get_all_vms_for_node(uid)
            files = []
            for vm in vms:
                params = {'dst': os.path.join(
                    self.task['parameters']['dst'],
                    '{0}_vm_conf.xml'.format(vm.id)),
                    'data': TemplateFormatter().format(template, **vm.params)}
                files.append(params)
            node['files'] = files
            nodes.append(node)
        yield templates.make_upload_files_task(uids, nodes)


class CreateVMsOnCompute(BaseVMSHook):
    """Hook that uploads info about all nodes in cluster."""

    identity = 'create_vms'
    hook_type = 'puppet'

    def serialize(self):
        uids = self.get_uids()
        yield templates.make_puppet_task(uids, self.task)


class UploadNodesInfo(GenericRolesHook):
    """Hook that uploads info about all nodes in cluster."""

    identity = 'upload_nodes_info'

    def serialize(self):
        q_nodes = objects.Cluster.get_nodes_not_for_deletion(self.cluster)
        # task can be executed only on deployed nodes
        nodes = set(q_nodes.filter_by(status=consts.NODE_STATUSES.ready))
        # add nodes scheduled for deployment since they could be filtered out
        # above and task must be run also on them
        nodes.update(self.nodes)

        uids = [n.uid for n in nodes]

        # every node must have data about every other good node in cluster
        serialized_nodes = self._serialize_nodes(nodes)
        data = yaml.safe_dump({
            'nodes': serialized_nodes,
        })

        path = self.task['parameters']['path']
        yield templates.make_upload_task(uids, path=path, data=data)

    def _serialize_nodes(self, nodes):
        serializer = deployment_serializers.get_serializer_for_cluster(
            self.cluster)
        net_serializer = serializer.get_net_provider_serializer(self.cluster)

        serialized_nodes = serializer.node_list(nodes)
        serialized_nodes = net_serializer.update_nodes_net_info(
            self.cluster, serialized_nodes)
        return serialized_nodes


class UpdateHosts(GenericRolesHook):
    """Updates hosts info on nodes in cluster."""

    identity = 'update_hosts'

    def serialize(self):
        q_nodes = objects.Cluster.get_nodes_not_for_deletion(self.cluster)
        # task can be executed only on deployed nodes
        nodes = set(q_nodes.filter_by(status=consts.NODE_STATUSES.ready))
        # add nodes scheduled for deployment since they could be filtered out
        # above and task must be run also on them
        nodes.update(self.nodes)

        uids = [n.uid for n in nodes]

        yield templates.make_puppet_task(uids, self.task)


class TaskSerializers(object):
    """Class serves as fabric for different types of task serializers."""

    stage_serializers = [UploadMOSRepo, RsyncPuppet, CopyKeys, RestartRadosGW,
                         UploadNodesInfo, UpdateHosts, GenerateKeys,
                         UploadVMSInfo]
    deploy_serializers = [PuppetHook, CreateVMsOnCompute]

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
        if getattr(serializer, 'identity', None):
            self._deploy_serializers_map[serializer.identity] = serializer
        else:
            self._deploy_serializers_map[serializer.hook_type] = serializer

    def get_deploy_serializer(self, task):
        if 'type' not in task:
            raise errors.InvalidData('Task %s should have type', task)

        if task.get('id') and task.get('id') in self._deploy_serializers_map:
            return self._deploy_serializers_map[task['id']]
        elif task['type'] in self._deploy_serializers_map:
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
