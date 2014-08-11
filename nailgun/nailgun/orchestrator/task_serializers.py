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

from nailgun.consts import ANY_ROLE
from nailgun import objects
from nailgun.orchestrator.priority_serializers import PriorityStrategy


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


def make_sync_scripts_task(src, dst):
    return {
        'type': 'sync',
        'parameters': {
            'src': src,
            'dst': dst}}


def make_shell_task(task, cwd='/'):
    return {
        'type': 'shell',
        'parameters': {
            'cmd': task['parameters']['cmd'],
            'timeout': task['parameters']['timeout'],
            'cwd': cwd}}


def make_puppet_task(task, cwd='/'):
    return {
        'type': 'puppet',
        'parameters': {
            'puppet_manifest': task['parameters']['puppet_manifest'],
            'puppet_modules': task['parameters']['puppet_modules'],
            'timeout': task['parameters']['timeout'],
            'cwd': cwd}}


class TaskDeploymentSerializer(object):

    task_types = {'puppet': make_puppet_task,
                  'shell': make_shell_task}

    def __init__(self, cluster):
        self.cluster = cluster
        self.tasks = objects.Cluster.get_tasks(cluster)

    def get_tasks_for_role(self, role):
        tasks = []
        priority = PriorityStrategy()
        for task in self.tasks:
            if self.validate_task(task, role):
                tasks.append(self.task_types[task['type']](task))
        priority.one_by_one(tasks)
        return tasks

    def validate_task(self, task, role):
        type_compat = task['type'] in self.task_types.keys()
        role_compat = role in task['role'] or task['role'] == ANY_ROLE
        return role_compat and type_compat
