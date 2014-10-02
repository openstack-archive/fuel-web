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

"""Serializer for plugins tasks"""


from nailgun import consts
from nailgun.errors import errors
from nailgun.logger import logger
from nailgun import objects
from nailgun.orchestrator.priority_serializers import PriorityStrategy
from nailgun.plugins.manager import PluginManager


def make_repo_task(uids, repo_data, repo_path):
    return {
        'type': 'upload_file',
        'uids': uids,
        'parameters': {
            'path': repo_path,
            'data': repo_data}}


def make_ubuntu_repo_task(plugin_name, repo_url, uids):
    repo_data = 'deb {0} /'.format(repo_url)
    repo_path = '/etc/apt/sources.list.d/{0}.list'.format(plugin_name)

    return make_repo_task(uids, repo_data, repo_path)


def make_centos_repo_task(plugin_name, repo_url, uids):
    repo_data = '\n'.join([
        '[{0}]',
        'name=Plugin {0} repository',
        'baseurl={1}',
        'gpgcheck=0']).format(plugin_name, repo_url)
    repo_path = '/etc/yum.repos.d/{0}.repo'.format(plugin_name)

    return make_repo_task(uids, repo_data, repo_path)


def make_sync_scripts_task(uids, src, dst):
    return {
        'type': 'sync',
        'uids': uids,
        'parameters': {
            'src': src,
            'dst': dst}}


def make_shell_task(uids, task, cwd):
    return {
        'type': 'shell',
        'uids': uids,
        'parameters': {
            'cmd': task['parameters']['cmd'],
            'timeout': task['parameters']['timeout'],
            'cwd': cwd}}


def make_puppet_task(uids, task, cwd):
    return {
        'type': 'puppet',
        'uids': uids,
        'parameters': {
            'puppet_manifest': task['parameters']['puppet_manifest'],
            'puppet_modules': task['parameters']['puppet_modules'],
            'timeout': task['parameters']['timeout'],
            'cwd': cwd}}


class BasePluginDeploymentHooksSerializer(object):

    def __init__(self, cluster, nodes):
        self.cluster = cluster
        self.nodes = nodes
        self.priority = PriorityStrategy()

    def deployment_tasks(self, plugins, stage):
        tasks = []

        for plugin in plugins:
            puppet_tasks = filter(
                lambda t: (t['type'] == 'puppet' and
                           t['stage'] == stage),
                plugin.tasks)
            shell_tasks = filter(
                lambda t: (t['type'] == 'shell' and
                           t['stage'] == stage),
                plugin.tasks)

            for task in shell_tasks:
                uids = self.get_uids_for_task(task)
                if not uids:
                    continue
                tasks.append(self.serialize_task(
                    plugin, task,
                    make_shell_task(uids, task, plugin.slaves_scripts_path)))

            for task in puppet_tasks:
                uids = self.get_uids_for_task(task)
                if not uids:
                    continue
                tasks.append(self.serialize_task(
                    plugin, task,
                    make_puppet_task(uids, task, plugin.slaves_scripts_path)))

        return tasks

    def get_uids_for_tasks(self, tasks):
        uids = []
        for task in tasks:
            if isinstance(task['role'], list):
                for node in self.nodes:
                    required_for_node = set(task['role']) & set(
                        objects.Node.get_all_roles(node)
                    )
                    if required_for_node:
                        uids.append(node.id)
            elif task['role'] == '*':
                uids.extend([n.id for n in self.nodes])
            else:
                logger.warn(
                    'Wrong task format, `role` should be a list or "*": %s',
                    task)

        return list(set(uids))

    def get_uids_for_task(self, task):
        return self.get_uids_for_tasks([task])

    def serialize_task(self, plugin, task_defaults, task):
        task.update(self.get_default_parameters(plugin, task_defaults))
        return task

    def get_default_parameters(self, plugin, task_defaults):
        return {'fail_on_error': task_defaults.get('fail_on_error', True),
                'diagnostic_name': plugin.full_name}


class PluginsPreDeploymentHooksSerializer(BasePluginDeploymentHooksSerializer):

    def serialize(self):
        tasks = []
        plugins = PluginManager.get_cluster_plugins_with_tasks(self.cluster)
        tasks.extend(self.create_repositories(plugins))
        tasks.extend(self.sync_scripts(plugins))
        tasks.extend(self.deployment_tasks(plugins))
        self.priority.one_by_one(tasks)

        return tasks

    def create_repositories(self, plugins):
        operating_system = self.cluster.release.operating_system
        if operating_system == 'CentOS':
            make_repo = make_centos_repo_task
        elif operating_system == 'Ubuntu':
            make_repo = make_ubuntu_repo_task
        else:
            raise errors.InvalidOperatingSystem(
                'Operating system {0} is invalid'.format(operating_system))

        repo_tasks = []
        for plugin in plugins:
            uids = self.get_uids_for_tasks(plugin.tasks)

            # If there are not nodes for tasks execution
            # or if there are no files in repository
            if not uids or not plugin.repo_files(self.cluster):
                continue

            repo_tasks.append(
                self.serialize_task(
                    plugin, {},
                    make_repo(plugin.full_name,
                              plugin.repo_url(self.cluster), uids)))

        return repo_tasks

    def sync_scripts(self, plugins):
        tasks = []
        for plugin in plugins:
            uids = self.get_uids_for_tasks(plugin.tasks)
            if not uids:
                continue
            tasks.append(
                self.serialize_task(
                    plugin, {},
                    make_sync_scripts_task(
                        uids,
                        plugin.master_scripts_path(self.cluster),
                        plugin.slaves_scripts_path)))

        return tasks

    def deployment_tasks(self, plugins):
        return super(
            PluginsPreDeploymentHooksSerializer, self).\
            deployment_tasks(plugins, consts.STAGES.pre_deployment)


class PluginsPostDeploymentHooksSerializer(
        BasePluginDeploymentHooksSerializer):

    def serialize(self):
        tasks = []
        plugins = PluginManager.get_cluster_plugins_with_tasks(self.cluster)
        tasks.extend(self.deployment_tasks(plugins))
        self.priority.one_by_one(tasks)
        return tasks

    def deployment_tasks(self, plugins):
        return super(
            PluginsPostDeploymentHooksSerializer, self).\
            deployment_tasks(plugins, consts.STAGES.post_deployment)


def pre_deployment_serialize(cluster, nodes):
    serializer = PluginsPreDeploymentHooksSerializer(cluster, nodes)
    return serializer.serialize()


def post_deployment_serialize(cluster, nodes):
    serializer = PluginsPostDeploymentHooksSerializer(cluster, nodes)
    return serializer.serialize()
