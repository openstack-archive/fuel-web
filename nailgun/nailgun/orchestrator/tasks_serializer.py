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
from collections import defaultdict
import os
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
from nailgun.utils.role_resolver import BaseRoleResolver


def get_uids_for_roles(nodes, roles):
    """Returns list of uids for nodes that matches roles

    :param nodes: list of nodes
    :param roles: list of roles or consts.TASK_ROLES.all
    :returns: list of strings
    """

    uids = set()

    if roles == consts.TASK_ROLES.all:
        uids.update([n.uid for n in nodes])
    elif roles == consts.TASK_ROLES.master:
        return [consts.MASTER_NODE_UID]
    elif isinstance(roles, list):
        for node in nodes:
            if set(roles) & set(objects.Node.all_roles(node)):
                uids.add(node.uid)
    else:
        logger.warn(
            'Wrong roles format, `roles` should be a list or "*": %s',
            roles)

    return list(uids)


class LegacyRoleResolver(BaseRoleResolver):
    """The role resolver that implements legacy behaviour."""

    # TODO(bgaifullin): remove this in 9.0
    def __init__(self, nodes):
        self.nodes = nodes

    def resolve(self, roles, policy=None):
        return get_uids_for_roles(self.nodes, roles)


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
                'settings':
                objects.Cluster.get_editable_attributes(self.cluster)}

    def should_execute(self):
        if 'condition' not in self.task:
            return True
        return Expression(
            self.task['condition'], self._expression_context).evaluate()


class GenericNodeHook(ExpressionBasedTask):
    """Should be used for node serialization."""

    hook_type = abc.abstractproperty

    def __init__(self, task, cluster, node):
        self.node = node
        super(GenericNodeHook, self).__init__(task, cluster)


class PuppetHook(GenericNodeHook):

    hook_type = 'puppet'

    def serialize(self):
        yield templates.make_puppet_task([
            self.node['uid']],
            self.task,
            objects.Cluster.get_editable_attributes(self.cluster)
            ['common']['puppet_retries']['value'])


class StandartConfigRolesHook(ExpressionBasedTask):
    """Role hooks that serializes task based on config file only."""

    def __init__(self, task, cluster, nodes, role_resolver=None):
        super(StandartConfigRolesHook, self).__init__(task, cluster)
        self.nodes = nodes
        self.role_resolver = role_resolver or LegacyRoleResolver(nodes)

    def get_uids(self):
        return self.role_resolver.resolve(
            self.task.get('role', self.task.get('groups'))
        )

    def serialize(self):
        uids = self.get_uids()
        if uids:
            yield templates.make_generic_task(uids, self.task)


class GenericRolesHook(StandartConfigRolesHook):

    identity = abc.abstractproperty


class UploadMOSRepo(GenericRolesHook):

    identity = 'upload_core_repos'

    def get_uids(self):
        return self.role_resolver.resolve(consts.TASK_ROLES.all)

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
                    'timeout': 60
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
        return self.role_resolver.resolve(consts.TASK_ROLES.all)

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


class GenerateCephKeys(GenerateKeys):

    identity = 'generate_keys_ceph'


class CopyCephKeys(CopyKeys):

    identity = 'copy_keys_ceph'


class GenerateHaproxyKeys(GenericRolesHook):

    identity = 'generate_haproxy_keys'

    def serialize(self):
        uids = self.get_uids()
        self.task['parameters']['cmd'] = self.task['parameters']['cmd'].format(
            CLUSTER_ID=self.cluster.id,
            CN_HOSTNAME=objects.Cluster.get_editable_attributes(self.cluster)
            ['public_ssl']['hostname']['value'])
        yield templates.make_shell_task(uids, self.task)


class CopyHaproxyKeys(CopyKeys):

    identity = 'copy_haproxy_keys'


class IronicUploadImages(GenericRolesHook):

    identity = 'ironic_upload_images'

    def serialize(self):
        uids = self.get_uids()
        if uids:
            self.task['parameters']['cmd'] = \
                self.task['parameters']['cmd'].format(
                    CLUSTER_ID=self.cluster.id)
            yield templates.make_shell_task(uids, self.task)


class IronicCopyBootstrapKey(CopyKeys):

    identity = 'ironic_copy_bootstrap_key'


class RestartRadosGW(GenericRolesHook):

    identity = 'restart_radosgw'

    def should_execute(self):
        for node in self.nodes:
            if 'ceph-osd' in node.all_roles:
                return True
        return False


class CreateVMsOnCompute(GenericRolesHook):
    """Hook that uploads info about all nodes in cluster."""

    identity = 'generate_vms'
    hook_type = 'puppet'

    def __init__(self, task, cluster, nodes, role_resolver=None):
        super(CreateVMsOnCompute, self).__init__(
            task, cluster, [], role_resolver
        )
        self.vm_nodes = objects.Cluster.get_nodes_to_spawn_vms(self.cluster)

    def should_execute(self):
        return len(self.vm_nodes) > 0

    def get_uids(self):
        return [node.uid for node in self.vm_nodes]

    def get_nodes(self):
        return self.vm_nodes

    def serialize(self):
        uids = self.get_uids()
        yield templates.make_puppet_task(
            uids,
            self.task,
            objects.Cluster.get_editable_attributes(self.cluster)
            ['common']['puppet_retries']['value'])


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

        yield templates.make_puppet_task(
            uids,
            self.task,
            objects.Cluster.get_editable_attributes(self.cluster)
            ['common']['puppet_retries']['value'])


class UploadConfiguration(GenericRolesHook):
    """Hook that uploads yaml file with configuration on nodes."""

    identity = 'upload_configuration'

    def __init__(self, task, cluster, nodes, configs=None, role_resolver=None):
        super(UploadConfiguration, self).__init__(
            task, cluster, nodes, role_resolver=role_resolver
        )
        self.configs = configs

    def serialize(self):
        configs = self.configs
        if configs is None:
            configs = objects.OpenstackConfigCollection.find_configs_for_nodes(
                self.cluster, self.nodes)

        node_configs = defaultdict(lambda: defaultdict(dict))
        nodes_to_update = dict((node.id, node) for node in self.nodes)

        for config in configs:

            if config.config_type == consts.OPENSTACK_CONFIG_TYPES.cluster:
                for node_id in nodes_to_update:
                    node_configs[node_id]['cluster'] = config.configuration

            elif config.config_type == consts.OPENSTACK_CONFIG_TYPES.role:
                for node in self.nodes:
                    if config.node_role in node.roles:
                        node_configs[node.id]['role'].update(
                            config.configuration)

            elif config.config_type == consts.OPENSTACK_CONFIG_TYPES.node:
                if config.node_id in nodes_to_update:
                    fqdn = objects.Node.get_node_fqdn(
                        nodes_to_update[config.node_id])
                    node_configs[config.node_id][fqdn] = config.configuration

        for node_id in node_configs:
            for config_dest in node_configs[node_id]:
                path = os.path.join(consts.OVERRIDE_CONFIG_BASE_PATH,
                                    config_dest + '.yaml')
                # Converts config from MutableDict to dict
                # needs for further serialization to yaml
                data = {
                    'configuration': dict(node_configs[node_id][config_dest])}
                node = nodes_to_update[node_id]
                yield templates.make_upload_task(
                    [node.uid], path=path, data=yaml.safe_dump(data))


class TaskSerializers(object):
    """Class serves as fabric for different types of task serializers."""

    stage_serializers = [UploadMOSRepo, RsyncPuppet, CopyKeys, RestartRadosGW,
                         UploadNodesInfo, UpdateHosts, GenerateKeys,
                         GenerateHaproxyKeys, CopyHaproxyKeys,
                         GenerateCephKeys, CopyCephKeys, IronicUploadImages,
                         IronicCopyBootstrapKey, UploadConfiguration]
    deploy_serializers = [PuppetHook, CreateVMsOnCompute]

    def __init__(self, stage_serializers=None, deploy_serializers=None):
        """TaskSerializers initializer

        Task serializers for stage (pre/post) are different from
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

        if task['id'] and task['id'] in self._deploy_serializers_map:
            return self._deploy_serializers_map[task['id']]
        elif task['type'] in self._deploy_serializers_map:
            return self._deploy_serializers_map[task['type']]
        else:
            # Currently we are not supporting anything except puppet as main
            # deployment engine, therefore exception should be raised,
            # but it should be verified by validation as well
            raise errors.SerializerNotSupported(
                'Serialization of type {0} is not supported. Task {1}'.format(
                    task['type'], task))

    def get_stage_serializer(self, task):
        if 'id' not in task:
            raise errors.InvalidData('Task %s should have id', task)

        if task['id'] in self._stage_serializers_map:
            return self._stage_serializers_map[task['id']]
        else:
            return StandartConfigRolesHook
