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

from nailgun.settings import settings

from nailgun.settings import settings
from urlparse import urljoin
import yaml
from nailgun.orchestrator.priority_serializers import PriorityStrategy
from nailgun.objects import Cluster

import glob
import os


class PluginData(object):
    """NOTE(eli): this stuff should be somewhere in object
    """

    def __init__(self, plugin_name, metadata, tasks):
        self.plugin_name = plugin_name
        self.metadata = metadata
        self.tasks = tasks

    def get_release_info(self, release):
        os = release.operating_system.lower()
        version = release.version

        release_info = filter(
            lambda r: (r['os'] == os and
                       r['version'] == version),
            self.metadata['releases'])

        return release_info[0]

    @property
    def full_name(self):
        return '{0}-{1}'.format(
            self.metadata['name'],
            self.metadata['version'])

    @property
    def slave_scripts_path(self):
        return settings.PLUGINS_SLAVES_SCRIPTS_PATH.format(
            plugin_name=self.full_name)

def get_plugins():
    plugin_directories = glob.glob(os.path.join(settings.PLUGINS_PATH, '*'))
    plugins = []
    for directory in plugin_directories:
        metadata_path = os.path.join(directory, 'metadata.yaml')
        tasks_path = os.path.join(directory, 'tasks.yaml')

        if not os.path.exists(metadata_path) or not os.path.exists(tasks_path):
            continue

        plugin_name = os.path.basename(directory)

        plugin_data = PluginData(
            plugin_name,
            yaml.load(open(metadata_path)),
            yaml.load(open(tasks_path)))
        plugins.append(plugin_data)

    return plugins


def get_plugins_for_cluster(cluster):
    plugins = get_plugins()
    enabled_plugins = []
    for plugin in plugins:
        # TODO(eli): is required only for development
        # it will be replaced with plugins <-> cluster
        # relation
        enabled = Cluster.get_attributes(cluster).editable.get(
            plugin.metadata['name'], {}).get('metadata', {}).get('enabled')

        if not enabled:
            continue
        enabled_plugins.append(plugin)

    return sorted(enabled_plugins, key=lambda p: p.full_name)


def make_repo_task(uids, repo_data, repo_path):
    return {
        'type': 'upload_file',
        'uids': uids,
        'parameters': {
            'path': repo_path,
            'data': repo_data}}


def make_ubuntu_repo_task(plugin_name, repo_url, uids):
    repo_data = ['deb {0}'.format(repo_url)]
    repo_path = '/etc/apt/sources.list.d/{0}.list'.format(plugin_name)

    return make_repo_task(uids, repo_data, repo_path)


def make_centos_repo_task(plugin_name, repo_url, uids):
    repo_data = "\n".join([
        '[{0}]'
        'name=Plugin {0} repository'
        'baseurl={1}'
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
                tasks.append(make_shell_task(
                    uids,
                    task,
                    plugin.slave_scripts_path))

            for task in puppet_tasks:
                uids = self.get_uids_for_task(task)
                if not uids:
                    continue
                tasks.append(make_puppet_task(
                    uids,
                    task,
                    plugin.slave_scripts_path))

        return tasks

    def get_uids_for_tasks(self, tasks):
        uids = []
        for task in tasks:
            if isinstance(task['role'], list):
                for node in self.nodes:
                    required_for_node = set(task['role']) & set(node.all_roles)
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


class PluginsPreDeploymentHooksSerializer(BasePluginDeploymentHooksSerializer):

    def serialize(self):
        tasks = []
        plugins = get_plugins_for_cluster(self.cluster)
        tasks.extend(self.create_repositories(plugins))
        tasks.extend(self.sync_scripts(plugins))
        tasks.extend(self.deployment_tasks(plugins))
        self.priority.one_by_one(tasks)

        return tasks

    def create_repositories(self, plugins):
        os = self.cluster.release.operating_system
        if os == 'CentOS':
            make_repo = make_centos_repo_task
        elif os == 'Ubuntu':
            make_repo = make_ubuntu_repo_task
        else:
            raise errors.InvalidOperatingSystem(
                'Operating system {0} is invalid'.format(os))

        repo_tasks = []
        for plugin in plugins:
            uids = self.get_uids_for_tasks(plugin.tasks)
            if not uids:
                continue
            repo_base = settings.PLUGINS_REPO_URL.format(
                master_ip=settings.MASTER_IP,
                plugin_name=plugin.full_name)

            release_info = plugin.get_release_info(self.cluster.release)
            repo_url = urljoin(repo_base, release_info['repository_path'])
            repo_tasks.append(make_repo(plugin.full_name, repo_url, uids))

        return repo_tasks

    def sync_scripts(self, plugins):
        tasks = []
        for plugin in plugins:
            uids = self.get_uids_for_tasks(plugin.tasks)
            if not uids:
                continue
            src = settings.PLUGINS_SLAVES_RSYNC.format(
                master_ip=settings.MASTER_IP,
                plugin_name=plugin.full_name)
            dst = plugin.slave_scripts_path
            tasks.append(make_sync_scripts_task(uids, src, dst))

        return tasks

    def deployment_tasks(self, plugins):
        return super(
            PluginsPreDeploymentHooksSerializer, self).\
            deployment_tasks(plugins, 'pre_deployment')


class PluginsPostDeploymentHooksSerializer(BasePluginDeploymentHooksSerializer):

    def serialize(self):
        tasks = []
        plugins = get_plugins_for_cluster(self.cluster)
        tasks.extend(self.deployment_tasks(plugins))
        self.priority.one_by_one(tasks)

        return tasks

    def deployment_tasks(self, plugins):
        return super(
            PluginsPostDeploymentHooksSerializer, self).\
            deployment_tasks(plugins, 'post_deployment')



def pre_deployment_serialize(cluster, nodes):
    serializer = PluginsPreDeploymentHooksSerializer(cluster, nodes)
    return serializer.serialize()


def post_deployment_serialize(cluster, nodes):
    serializer = PluginsPostDeploymentHooksSerializer(cluster, nodes)
    return serializer.serialize()
