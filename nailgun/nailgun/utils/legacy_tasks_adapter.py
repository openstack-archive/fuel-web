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
import itertools

from nailgun import consts
from nailgun.logger import logger


def _get_role(task):
    return task.get('roles', task.get('groups'))


def _get_task_stage(task):
    return task['stage'].split('/')[0]


def _get_task_stage_and_priority(task):
    stage_list = task['stage'].split('/')
    stage = stage_list[0]
    priority = stage_list[-1] if len(stage_list) > 1 else 0
    try:
        priority = float(priority)
    except ValueError:
        logger.warn(
            'Task %s has non numeric priority "%s", set to 0',
            task, priority)
        priority = 0
    return stage, priority


def adapt_legacy_tasks(deployment_tasks, stage_tasks, role_resolver):
    """Adapt the legacy tasks to execute with Task Based Engine.

    :param deployment_tasks: the list of deployment tasks
    :param stage_tasks: the pre/post deployment tasks
    :param role_resolver: the RoleResolver instance
    """
    min_task_version = StrictVersion(consts.TASK_CROSS_DEPENDENCY)
    task_start_template = '{0}_start'
    task_end_template = '{0}_end'

    groups = {}
    sync_points = []
    legacy_tasks = []
    for task in deployment_tasks:
        task_type = task.get('type')
        task_version = StrictVersion(task.get('version', '0.0.0'))
        if task_type == consts.ORCHESTRATOR_TASK_TYPES.group:
            task = task.copy()
            task['cross_depends'] = [{'name': 'deploy_start', 'role': None}]
            task['cross_depended_by'] = [{'name': 'deploy_end', 'role': None}]
            groups[task['id']] = task
        elif task_type == consts.ORCHESTRATOR_TASK_TYPES.stage:
            sync_points.append(task)
        else:
            task = task.copy()
            required_for = copy.copy(task.get('required_for', []))
            required_for.extend(
                task_end_template.format(x)
                for x in role_resolver.get_all_roles(_get_role(task))
            )
            task['required_for'] = required_for
            if task_version < min_task_version:
                legacy_tasks.append(task)
                continue
        yield task

    if not (legacy_tasks or stage_tasks):
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

    stage_tasks.sort(key=_get_task_stage_and_priority)
    for stage, tasks in itertools.groupby(stage_tasks, key=_get_task_stage):
        anchor_name = '{0}_end'.format(stage)
        cross_depends = [{'name': anchor_name, 'role': None}]
        for sync_point in sync_points:
            if anchor_name in sync_point.get('requires', ()):
                cross_depended_by = [{'name': sync_point['id'], 'role': None}]
                break
        else:
            cross_depended_by = []

        for idx, task in enumerate(tasks):
            task = copy.copy(task)
            task['id'] = '{0}_{1}'.format(stage, idx)
            task['cross_depends'] = cross_depends
            task['cross_depended_by'] = cross_depended_by
            yield task
            cross_depends = [{'name': task['id'], 'roles': task['roles']}]
