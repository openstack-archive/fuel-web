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
from nailgun.settings import settings


class BasePluginDeploymentHooksSerializer(object):
    # TODO(dshulyak) refactor it to be consistent with task_serializer

    def __init__(self, cluster, nodes):
        self.cluster = cluster
        self.nodes = nodes

    def deployment_tasks(self, plugins, stage):
        tasks = []
        plugin_tasks = []
        sorted_plugins = sorted(plugins, key=lambda p: p.plugin.name)

        for plugin in sorted_plugins:
            stage_tasks = filter(
                lambda t: t['stage'].startswith(stage), plugin.tasks)
            plugin_tasks.extend(self._set_tasks_defaults(plugin, stage_tasks))

        sorted_tasks = self._sort_by_stage_postfix(plugin_tasks)
        for task in sorted_tasks:
            make_task = None
            uids = get_uids_for_roles(self.nodes, task['role'])
            if not uids:
                continue

            if task['type'] == 'shell':
                make_task = templates.make_shell_task
            elif task['type'] == 'puppet':
                make_task = templates.make_puppet_task
            elif task['type'] == 'reboot':
                make_task = templates.make_reboot_task
            else:
                logger.warn('Task is skipped {0}, because its type is '
                            'not supported').format(task)

            if make_task:
                tasks.append(self._serialize_task(make_task(uids, task), task))

        return tasks

    def _set_tasks_defaults(self, plugin, tasks):
        for task in tasks:
            self._set_task_defaults(plugin, task)
        return tasks

    def _set_task_defaults(self, plugin, task):
        task['parameters'].setdefault('cwd', plugin.slaves_scripts_path)
        task.setdefault('diagnostic_name', plugin.full_name)
        task.setdefault('fail_on_error', True)

        return task

    def _serialize_task(self, task, default_task):
        task.update({
            'diagnostic_name': default_task['diagnostic_name'],
            'fail_on_error': default_task['fail_on_error']})
        return task

    def serialize_task(self, plugin, task):
        return self._serialize_task(
            self._set_task_defaults(plugin, task), task)

    def _sort_by_stage_postfix(self, tasks):
        """Sorts tasks by task postfixes

        for example here are several tasks' stages:

        stage: post_deployment/100
        stage: post_deployment
        stage: post_deployment/-100

        The method returns tasks in the next order

        stage: post_deployment/-100
        stage: post_deployment # because by default postifx is 0
        stage: post_deployment/100
        """
        def postfix(task):
            stage_list = task['stage'].split('/')
            postfix = stage_list[-1] if len(stage_list) > 1 else 0

            try:
                postfix = float(postfix)
            except ValueError:
                logger.warn(
                    'Task %s has non numeric postfix "%s", set to 0',
                    task, postfix)
                postfix = 0

            return postfix

        return sorted(tasks, key=postfix)


class PluginsPreDeploymentHooksSerializer(BasePluginDeploymentHooksSerializer):

    def serialize(self):
        tasks = []
        plugins = PluginManager.get_cluster_plugins_with_tasks(self.cluster)
        tasks.extend(self.create_repositories(plugins))
        tasks.extend(self.sync_scripts(plugins))
        tasks.extend(self.deployment_tasks(plugins))
        return tasks

    def _get_node_uids_for_plugin_tasks(self, plugin):
        # TODO(aroma): remove concatenation of tasks when unified way of
        # processing will be introduced for deployment tasks and existing
        # plugin tasks
        tasks_to_process = plugin.tasks + plugin.deployment_tasks

        uids = get_uids_for_tasks(self.nodes, tasks_to_process)

        # NOTE(aroma): pre-deployment tasks should not be executed on
        # master node because in some cases it leads to errors due to
        # commands need to be run are not compatible with master node
        # OS (CentOS). E.g. of such situation - create repository
        # executes `apt-get update` which fails on CentOS
        if consts.MASTER_NODE_UID in uids:
            uids.remove(consts.MASTER_NODE_UID)

        return uids

    def create_repositories(self, plugins):
        operating_system = self.cluster.release.operating_system

        repo_tasks = []
        for plugin in plugins:
            uids = self._get_node_uids_for_plugin_tasks(plugin)

            # If there are no nodes for tasks execution
            # or if there are no files in repository
            if not uids or not plugin.repo_files(self.cluster):
                continue

            if operating_system == consts.RELEASE_OS.centos:
                repo = self.get_centos_repo(plugin)
                repo_tasks.append(
                    self.serialize_task(
                        plugin,
                        templates.make_centos_repo_task(uids, repo)))

            elif operating_system == consts.RELEASE_OS.ubuntu:
                repo = self.get_ubuntu_repo(plugin)

                repo_tasks.append(
                    self.serialize_task(
                        plugin,
                        templates.make_ubuntu_sources_task(uids, repo)))

                # do not add preferences task to task list if we can't
                # complete it (e.g. can't retrieve or parse Release file)
                task = templates.make_ubuntu_preferences_task(uids, repo)
                if task is not None:
                    repo_tasks.append(self.serialize_task(plugin, task))

                # apt-get update executed after every additional source.list
                # to be able understand what plugin source.list caused error
                repo_tasks.append(
                    self.serialize_task(
                        plugin,
                        templates.make_apt_update_task(uids)))
            else:
                raise errors.InvalidOperatingSystem(
                    'Operating system {0} is invalid'.format(operating_system))

        return repo_tasks

    def sync_scripts(self, plugins):
        tasks = []
        for plugin in plugins:
            uids = self._get_node_uids_for_plugin_tasks(plugin)

            if not uids:
                continue

            tasks.append(
                self.serialize_task(
                    plugin,
                    templates.make_sync_scripts_task(
                        uids,
                        plugin.master_scripts_path(self.cluster),
                        plugin.slaves_scripts_path)))

        return tasks

    def deployment_tasks(self, plugins):
        return super(
            PluginsPreDeploymentHooksSerializer, self).\
            deployment_tasks(plugins, consts.STAGES.pre_deployment)

    def get_centos_repo(self, plugin):
        return {
            'type': 'rpm',
            'name': plugin.full_name,
            'uri': plugin.repo_url(self.cluster),
            'priority': settings.REPO_PRIORITIES['plugins']['centos']}

    def get_ubuntu_repo(self, plugin):
        return {
            'type': 'deb',
            'name': plugin.full_name,
            'uri': plugin.repo_url(self.cluster),
            'suite': '/',
            'section': '',
            'priority': settings.REPO_PRIORITIES['plugins']['ubuntu']}


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
