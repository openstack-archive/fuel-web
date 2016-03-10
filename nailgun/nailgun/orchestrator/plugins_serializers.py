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

import itertools

from nailgun import consts
from nailgun.errors import errors
from nailgun.logger import logger
import nailgun.orchestrator.tasks_templates as templates
from nailgun.settings import settings
from nailgun.utils.role_resolver import RoleResolver

# TODO(bgaifullin) HUCK to prevent cycle imports
from nailgun.plugins.manager import PluginManager


class BasePluginDeploymentHooksSerializer(object):
    # TODO(dshulyak) refactor it to be consistent with task_serializer

    def __init__(self, cluster, nodes, role_resolver=None):
        """Initialises.

        :param cluster: the cluster object instance
        :param nodes: the list of nodes for deployment
        :param role_resolver: the instance of BaseRoleResolver
        """

        self.cluster = cluster
        self.nodes = nodes
        self.role_resolver = role_resolver or RoleResolver(nodes)

    def deployment_tasks(self, plugins, stage):
        plugin_tasks = []
        sorted_plugins = sorted(plugins, key=lambda p: p.plugin.name)

        for plugin in sorted_plugins:
            stage_tasks = filter(
                lambda t: t['stage'].startswith(stage), plugin.tasks)
            plugin_tasks.extend(self._set_tasks_defaults(plugin, stage_tasks))

        sorted_tasks = self._sort_by_stage_postfix(plugin_tasks)
        for task in sorted_tasks:
            make_task = None
            uids = self.role_resolver.resolve(task['role'])
            if not uids:
                continue

            if task['type'] == 'shell':
                make_task = templates.make_shell_task
            elif task['type'] == 'puppet':
                make_task = templates.make_puppet_task
            elif task['type'] == 'reboot':
                make_task = templates.make_reboot_task
            else:
                logger.warn('Task is skipped %s, because its type is '
                            'not supported', task)

            if make_task:
                yield self._serialize_task(make_task(uids, task), task)

    def _set_tasks_defaults(self, plugin, tasks):
        for task in tasks:
            self._set_task_defaults(plugin, task)
        return tasks

    @staticmethod
    def _set_task_defaults(plugin, task):
        task['parameters'].setdefault('cwd', plugin.slaves_scripts_path)
        task.setdefault('diagnostic_name', plugin.full_name)
        task.setdefault('fail_on_error', True)

        return task

    @staticmethod
    def _serialize_task(task, default_task):
        task.update({
            'diagnostic_name': default_task['diagnostic_name'],
            'fail_on_error': default_task['fail_on_error']})
        return task

    def serialize_task(self, plugin, task):
        return self._serialize_task(
            self._set_task_defaults(plugin, task), task)

    @staticmethod
    def _sort_by_stage_postfix(tasks):
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
        def get_postfix(task):
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

        return sorted(tasks, key=get_postfix)


class PluginsPreDeploymentHooksSerializer(BasePluginDeploymentHooksSerializer):

    def serialize_begin_tasks(self):
        plugins = PluginManager.get_enabled_plugins(self.cluster)
        return itertools.chain(
            self.create_repositories(plugins),
            self.sync_scripts(plugins))

    def serialize_end_tasks(self):
        plugins = PluginManager.get_enabled_plugins(self.cluster)
        return self.deployment_tasks(plugins)

    def _get_node_uids_for_plugin_tasks(self, plugin):
        # TODO(aroma): remove concatenation of tasks when unified way of
        # processing will be introduced for deployment tasks and existing
        # plugin tasks
        tasks_to_process = plugin.tasks + plugin.deployment_tasks

        roles = []
        for task in tasks_to_process:
            # plugin tasks may store information about node
            # role not only in `role` key but also in `groups`
            task_role = task.get('role', task.get('groups'))
            if task_role == consts.TASK_ROLES.all:
                # just return all nodes
                return self.role_resolver.resolve(consts.TASK_ROLES.all)
            elif task_role == consts.TASK_ROLES.master:
                # NOTE(aroma): pre-deployment tasks should not be executed on
                # master node because in some cases it leads to errors due to
                # commands need to be run are not compatible with master node
                # OS (CentOS). E.g. of such situation - create repository
                # executes `apt-get update` which fails on CentOS
                continue
            elif isinstance(task_role, list):
                roles.extend(task_role)
            # if task has 'skipped' status it is allowed that 'roles' and
            # 'groups' are not be specified
            elif task['type'] != consts.ORCHESTRATOR_TASK_TYPES.skipped:
                logger.warn(
                    'Wrong roles format in task %s: either '
                    '`roles` or `groups` must be specified and contain '
                    'a list of roles or "*"',
                    task)

        return self.role_resolver.resolve(roles)

    def create_repositories(self, plugins):
        operating_system = self.cluster.release.operating_system

        for plugin in plugins:
            uids = self._get_node_uids_for_plugin_tasks(plugin)

            # If there are no nodes for tasks execution
            # or if there are no files in repository
            if not uids or not plugin.repo_files(self.cluster):
                continue

            if operating_system == consts.RELEASE_OS.centos:
                repo = self.get_centos_repo(plugin)
                yield self.serialize_task(
                    plugin,
                    templates.make_centos_repo_task(uids, repo)
                )

            elif operating_system == consts.RELEASE_OS.ubuntu:
                repo = self.get_ubuntu_repo(plugin)
                yield self.serialize_task(
                    plugin,
                    templates.make_ubuntu_sources_task(uids, repo)
                )

                # do not add preferences task to task list if we can't
                # complete it (e.g. can't retrieve or parse Release file)
                task = templates.make_ubuntu_preferences_task(uids, repo)
                if task is not None:
                    yield self.serialize_task(plugin, task)

                # apt-get update executed after every additional source.list
                # to be able understand what plugin source.list caused error
                yield self.serialize_task(
                    plugin,
                    templates.make_apt_update_task(uids)
                )
            else:
                raise errors.InvalidOperatingSystem(
                    'Operating system {0} is invalid'.format(operating_system))

    def sync_scripts(self, plugins):
        for plugin in plugins:
            uids = self._get_node_uids_for_plugin_tasks(plugin)

            if not uids:
                continue

            yield self.serialize_task(
                plugin,
                templates.make_sync_scripts_task(
                    uids,
                    plugin.master_scripts_path(self.cluster),
                    plugin.slaves_scripts_path)
            )

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

    def serialize_begin_tasks(self):
        return list()

    def serialize_end_tasks(self):
        plugins = PluginManager.get_enabled_plugins(self.cluster)
        return self.deployment_tasks(plugins)

    def deployment_tasks(self, plugins):
        return super(
            PluginsPostDeploymentHooksSerializer, self).\
            deployment_tasks(plugins, consts.STAGES.post_deployment)
