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
from nailgun.orchestrator.tasks_serializer import get_uids_for_roles
from nailgun.orchestrator.tasks_serializer import get_uids_for_tasks
import nailgun.orchestrator.tasks_templates as templates
from nailgun.plugins.manager import PluginManager


class BasePluginDeploymentHooksSerializer(object):
    #TODO(dshulyak) refactor it to be consistent with task_serializer

    def __init__(self, cluster, nodes):
        self.cluster = cluster
        self.nodes = nodes

    def deployment_tasks(self, plugins, stage):
        tasks = []

        for plugin in plugins:
            plugin_tasks = filter(
                lambda t: (t['stage'] == stage),
                plugin.tasks)

            for task in plugin_tasks:
                uids = get_uids_for_roles(self.nodes, task['role'])
                if not uids:
                    continue
                if task['type'] == 'shell':
                    tasks.append(self.serialize_task(
                        plugin, task,
                        templates.make_shell_task(
                            uids, task, plugin.slaves_scripts_path)))
                elif task['type'] == 'puppet':
                    tasks.append(self.serialize_task(
                        plugin, task,
                        templates.make_puppet_task(
                            uids, task, plugin.slaves_scripts_path)))
                elif task['type'] == 'reboot':
                    tasks.append(self.serialize_task(
                        plugin, task,
                        templates.make_reboot_task(
                            uids, task)))
                else:
                    logger.warn('Task is skipped {0}, because its type is '
                                'not supported').format(task)

        return tasks

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
        return tasks

    def create_repositories(self, plugins):
        operating_system = self.cluster.release.operating_system

        repo_tasks = []
        for plugin in plugins:
            uids = get_uids_for_tasks(self.nodes, plugin.tasks)

            # If there are not nodes for tasks execution
            # or if there are no files in repository
            if not uids or not plugin.repo_files(self.cluster):
                continue

            if operating_system == consts.RELEASE_OS.centos:
                repo_tasks.append(
                    self.serialize_task(
                        plugin, {},
                        templates.make_centos_repo_task({
                            'type': 'rpm',
                            'name': plugin.full_name,
                            'uri': plugin.repo_url(self.cluster),
                            'priority': 1}, uids)))
            elif operating_system == consts.RELEASE_OS.ubuntu:
                repo_tasks.append(
                    self.serialize_task(
                        plugin, {},
                        templates.make_ubuntu_sources_task({
                            'type': 'deb',
                            'name': plugin.full_name,
                            'uri': plugin.repo_url(self.cluster),
                            'suite': '/',
                            'section': ''}, uids)))
                        # NOTE(kozhukalov) maybe here we also need to put
                        # preferences file to make sure plugin repo has
                        # a suitable priority level

                #apt-get upgrade executed after every additional source.list
                #to be able understand what plugin source.list caused error
                repo_tasks.append(
                    self.serialize_task(
                        plugin, {},
                        templates.make_apt_update_task(uids)))
            else:
                raise errors.InvalidOperatingSystem(
                    'Operating system {0} is invalid'.format(operating_system))

        return repo_tasks

    def sync_scripts(self, plugins):
        tasks = []
        for plugin in plugins:
            uids = get_uids_for_tasks(self.nodes, plugin.tasks)
            if not uids:
                continue
            tasks.append(
                self.serialize_task(
                    plugin, {},
                    templates.make_sync_scripts_task(
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
        return tasks

    def deployment_tasks(self, plugins):
        return super(
            PluginsPostDeploymentHooksSerializer, self).\
            deployment_tasks(plugins, consts.STAGES.post_deployment)
