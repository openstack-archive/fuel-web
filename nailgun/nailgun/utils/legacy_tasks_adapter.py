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

import copy
from distutils.version import StrictVersion

from nailgun import consts


def _get_role(task):
    return task.get('roles', task.get('groups'))


def adapt_legacy_tasks(deployment_tasks, role_resolver):
    """Adapt the legacy tasks to execute with Task Based Engine.

    :param deployment_tasks: the list of deployment tasks
    :param role_resolver: the RoleResolver instance
    """
    min_task_version = StrictVersion(consts.TASK_CROSS_DEPENDENCY)
    task_start_template = '{0}_start'
    task_end_template = '{0}_end'

    groups = {}
    legacy_tasks = []
    for task in deployment_tasks:
        task_type = task.get('type')
        task_version = StrictVersion(task.get('version', '0.0.0'))
        if task_type == consts.ORCHESTRATOR_TASK_TYPES.group:
            task = copy.deepcopy(task)
            task['cross_depends'] = [{'name': 'deploy_start', 'role': None}]
            task['cross_depended_by'] = [{'name': 'deploy_end', 'role': None}]
            groups[task['id']] = task
        elif task_type != consts.ORCHESTRATOR_TASK_TYPES.stage:
            task = copy.deepcopy(task)
            task.setdefault('required_for', []).extend(
                task_end_template.format(x)
                for x in role_resolver.get_all_roles(_get_role(task))
            )
            if task_version < min_task_version:
                legacy_tasks.append(task)
                continue
        yield task

    if not legacy_tasks:
        return

    for group in groups:
        for req in group.get('requires', ()):
            if req in groups:
                group['cross_depends'].append(
                    {
                        'name': task_end_template.format(req),
                        'role': _get_role(groups[req])
                    }
                )
        for req in group.get('required_for', ()):
            if req in groups:
                groups[req]['cross_depends'].append(
                    {
                        'name': task_end_template.format(group['id']),
                        'role': _get_role(group)
                    }
                )

    for group in groups:
        yield {
            'id': task_start_template.format(group['id']),
            'type': consts.ORCHESTRATOR_TASK_TYPES.skipped,
            'cross_depends': group['cross_depends']
        }
        yield {
            'id': task_end_template.format(group['id']),
            'type': consts.ORCHESTRATOR_TASK_TYPES.skipped,
            'cross_depends': [
                {
                    'name': task_start_template.format(group['id']),
                    'role': 'self'
                }
            ]
        }

    for task in legacy_tasks:
        roles = role_resolver.get_all_roles(_get_role(task))
        task['cross_depends'] = [
            {
                'name': task_start_template.format(r),
                'role': 'self'
            }
            for r in roles
        ]
        task['cross_depended_by'] = [
            {
                'name': task_end_template.format(r),
                'role': 'self'
            }
            for r in roles
        ]
        yield task
