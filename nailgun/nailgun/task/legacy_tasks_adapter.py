# -*- coding: utf-8 -*-

#    Copyright 2016 Mirantis, Inc.
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
from nailgun.orchestrator.orchestrator_graph import GraphSolver

TASK_START_TEMPLATE = '{0}_start'
TASK_END_TEMPLATE = '{0}_end'


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


def _join_groups(groups):
    for group in groups.values():
        for req in group.get('requires', ()):
            if req in groups:
                group['cross_depends'].append({
                    'name': TASK_END_TEMPLATE.format(req),
                    'role': _get_role(groups[req])
                })
        for req in group.get('required_for', ()):
            if req in groups:
                groups[req]['cross_depends'].append({
                    'name': TASK_END_TEMPLATE.format(group['id']),
                    'role': _get_role(group)
                })


def _get_group_start(group):
    return {
        'id': TASK_START_TEMPLATE.format(group['id']),
        'type': consts.ORCHESTRATOR_TASK_TYPES.skipped,
        'version': consts.TASK_CROSS_DEPENDENCY,
        'roles': _get_role(group),
        'cross_depends': group['cross_depends'],
        'cross_depended_by': [{
            'name': TASK_END_TEMPLATE.format(group['id']), 'role': 'self'
        }],
    }


def _get_group_end(group):
    return {
        'id': TASK_END_TEMPLATE.format(group['id']),
        'type': consts.ORCHESTRATOR_TASK_TYPES.skipped,
        'version': consts.TASK_CROSS_DEPENDENCY,
        'roles': _get_role(group)
    }


def _join_task_to_group(task, groups):
    task['version'] = consts.TASK_CROSS_DEPENDENCY
    # add only depends to start, because depends to end already added
    task['cross_depends'] = [
        {'name': TASK_START_TEMPLATE.format(g), 'role': 'self'} for g in groups
    ]
    return task


def adapt_legacy_tasks(deployment_tasks, legacy_plugin_tasks, role_resolver):
    """Adapt the legacy tasks to execute with Task Based Engine.

    :param deployment_tasks: the list of deployment tasks
    :param legacy_plugin_tasks: the pre/post tasks from tasks.yaml
    :param role_resolver: the RoleResolver instance
    """
    min_task_version = StrictVersion(consts.TASK_CROSS_DEPENDENCY)

    groups = {}
    sync_points = GraphSolver()
    legacy_tasks = []
    for task in deployment_tasks:
        task_type = task.get('type')
        task_version = StrictVersion(task.get('version', '0.0.0'))
        if task_type == consts.ORCHESTRATOR_TASK_TYPES.group:
            groups[task['id']] = dict(task, cross_depends=[])
        elif task_type == consts.ORCHESTRATOR_TASK_TYPES.stage:
            sync_points.add_task(task)
        else:
            task = task.copy()
            required_for = copy.copy(task.get('required_for', []))
            required_for.extend(
                TASK_END_TEMPLATE.format(x)
                for x in role_resolver.get_all_roles(_get_role(task))
            )
            task['required_for'] = required_for
            if task_version < min_task_version:
                legacy_tasks.append(task)
                continue
        yield task

    if not (legacy_tasks or legacy_plugin_tasks):
        return

    _join_groups(groups)

    # make bubbles from each group
    for group in groups.values():
        yield _get_group_start(group)
        yield _get_group_end(group)

    # put legacy tasks into bubble
    for task in legacy_tasks:
        logger.warning("Added cross_depends for legacy task: %s", task['id'])
        yield _join_task_to_group(
            task, role_resolver.get_all_roles(_get_role(task))
        )

    if not legacy_plugin_tasks:
        return

    # process tasks from stages
    legacy_plugin_tasks.sort(key=_get_task_stage_and_priority)
    tasks_per_stage = itertools.groupby(
        legacy_plugin_tasks, key=_get_task_stage
    )
    for stage, tasks in tasks_per_stage:
        sync_point_name = TASK_END_TEMPLATE.format(stage)
        cross_depends = [{'name': sync_point_name, 'role': None}]
        successors = sync_points.successors(sync_point_name)
        if successors:
            logger.debug(
                'The next stage is found for %s: %s',
                sync_point_name, successors[0]
            )
            cross_depended_by = [{'name': successors[0], 'role': None}]
        else:
            logger.debug(
                'The next stage is not found for %s.', sync_point_name
            )
            cross_depended_by = []

        for idx, task in enumerate(tasks):
            new_task = {
                'id': '{0}_{1}'.format(stage, idx),
                'type': task['type'],
                'roles': _get_role(task),
                'version': consts.TASK_CROSS_DEPENDENCY,
                'cross_depends': cross_depends,
                'cross_depended_by': cross_depended_by,
                'parameters': task.get('parameters', {}),
                'condition': task.get('condition', True)
            }
            cross_depends = [
                {'name': new_task['id'], 'role': new_task['roles']}
            ]
            yield new_task
