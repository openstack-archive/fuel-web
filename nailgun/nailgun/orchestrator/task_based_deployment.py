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

from collections import defaultdict
from copy import deepcopy
from distutils.version import StrictVersion
import random
import re

import six

from nailgun import consts
from nailgun.errors import errors
from nailgun.logger import logger
from nailgun import objects
from nailgun.orchestrator.tasks_serializer import CreateVMsOnCompute
from nailgun.orchestrator.tasks_serializer import DeploymentHook
from nailgun.orchestrator.tasks_serializer import RoleResolvePolicy
from nailgun.orchestrator.tasks_serializer import TaskSerializers
from nailgun.orchestrator.tasks_templates import make_noop_task


class PatternBasedRoleResolvePolicy(RoleResolvePolicy):
    """Helper class to find nodes by role."""

    def __init__(self, nodes):
        self.mapping = defaultdict(set)
        for node in nodes:
            for r in objects.Node.all_roles(node):
                self.mapping[r].add(node.uid)

    def resolve(self, roles):
        """Gets the nodes by role.

        :param roles: the required roles
        :type roles: list|str
        :return: the set of nodes
        """
        if roles == consts.ALL_ROLES:
            return set(
                uid for nodes in six.itervalues(self.mapping) for uid in nodes
            )
        if roles == consts.MASTER_ROLE:
            return set((consts.MASTER_ROLE,))

        result = set()
        if isinstance(roles, (list, tuple)):
            for role in roles:
                pattern = re.compile(role)
                for node_role, nodes_ids in six.iteritems(self.mapping):
                    if pattern.match(node_role):
                        result.update(self.mapping[role])
        else:
            logger.warn(
                'Wrong roles format, `roles` should be a list or "*": %s',
                roles
            )
        return result


class NoopSerializer(DeploymentHook):
    def __init__(self, task, *args, **kwargs):
        super(NoopSerializer, self).__init__()
        self.task = task

    def serialize(self):
        yield make_noop_task(self.task)


class DeploymentTaskSerializer(TaskSerializers):
    noop_task_types = (
        consts.ORCHESTRATOR_TASK_TYPES.skipped,
        consts.ORCHESTRATOR_TASK_TYPES.stage
    )

    def __init__(self):
        super(DeploymentTaskSerializer, self).__init__(
            TaskSerializers.stage_serializers + [CreateVMsOnCompute], []
        )

    def get_stage_serializer(self, task):
        if task.get('type') in self.noop_task_types:
            return NoopSerializer
        return super(DeploymentTaskSerializer, self).get_stage_serializer(
            task
        )


class TasksSerializer(object):
    task_attributes_to_copy = (
        'id', 'type', 'requires', 'required_for',
        'cross-depends', 'cross-depends-for'
    )

    def __init__(self, cluster, nodes):
        self.cluster = cluster
        self.role_resolver = PatternBasedRoleResolvePolicy(nodes)
        self.task_serializer = DeploymentTaskSerializer()

    @classmethod
    def serialize(cls, cluster, nodes, tasks):
        """Resolves roles and dependencies for tasks.

        :param cluster: the cluster instance
        :param nodes: the list of nodes
        :param tasks: the list of tasks
        :return: the list of serialized task per node
        """
        serializer = cls(cluster, nodes)
        tasks_per_node = serializer.resolve_nodes(tasks, nodes)
        serializer.resolve_dependencies(tasks_per_node)
        return dict(
            (k, list(six.itervalues(v)))
            for k, v in six.iteritems(tasks_per_node)
        )

    def resolve_nodes(self, tasks, nodes):
        """Resolves node roles in tasks.

        :param tasks: the deployment tasks
        :param nodes: the list of nodes to deploy
        :return the mapping tasks per node
        """
        tasks_per_node = defaultdict(dict)
        tasks_mapping = dict()
        tasks_groups = defaultdict(set)

        for task in tasks:
            if task.get('type') == consts.ORCHESTRATOR_TASK_TYPES.group:
                tasks_for_role = task.get('tasks')
                if tasks_for_role:
                    tasks_groups[tuple(task.get('role', []))].update(
                        tasks_for_role
                    )
                continue

            serializer_factory = self.task_serializer.get_stage_serializer(
                task
            )
            task_serializer = serializer_factory(
                task, self.cluster, nodes, roles_resolver=self.role_resolver
            )

            skipped = task.get('skipped') or \
                task.get('type') == consts.ORCHESTRATOR_TASK_TYPES.skipped or \
                not task_serializer.should_execute()

            for astute_task in task_serializer.serialize():
                # checks only for actual tasks
                if not self.is_task_based_deployment_allowed(task):
                    raise errors.TaskBaseDeploymentNotAllowed

                for attr in self.task_attributes_to_copy:
                    astute_task[attr] = task.get(attr)

                if skipped:
                    astute_task['skipped'] = True

                tasks_mapping[astute_task['id']] = astute_task

                for node_id in astute_task['uids']:
                    node_tasks = tasks_per_node[node_id]
                    if astute_task['id'] in node_tasks:
                        continue
                    node_tasks[astute_task['id']] = deepcopy(astute_task)

        for roles, task_ids in six.iteritems(tasks_groups):
            for node_id in self.role_resolver.resolve(roles):
                node_tasks = tasks_per_node[node_id]
                for task_id in task_ids:
                    if task_id in node_tasks:
                        continue
                    try:
                        node_tasks[task_id] = deepcopy(tasks_mapping[task_id])
                    except KeyError:
                        raise errors.InvalidData(
                            'Task %s cannot be resolved', task_id
                        )

        return tasks_per_node

    def resolve_dependencies(self, tasks_per_node):
        """Resolves tasks dependencies.

        :param tasks_per_node: the task per node mapping
        """
        for node_id, tasks in six.iteritems(tasks_per_node):
            for task in six.itervalues(tasks):
                task['requires'] = list(
                    self.expand_dependencies(
                        node_id, tasks_per_node, task.get('requires')
                    )
                )
                task['required_for'] = list(
                    self.expand_dependencies(
                        node_id, tasks_per_node, task.get('required_for')
                    )
                )
                task['requires'].extend(
                    self.expand_cross_dependencies(
                        tasks_per_node,
                        task.pop('cross-depends')
                    )
                )

                task['required_for'].extend(
                    self.expand_cross_dependencies(
                        tasks_per_node,
                        task.pop('cross-depends-for')
                    )
                )

    def expand_dependencies(self, node_id, tasks_per_node, dependencies):
        """Expands task dependencies on same node.

        :param node_id: the ID of node
        :param tasks_per_node: the task per node mapping
        :param dependencies: the list of dependencies on same node
        """
        if not dependencies:
            return

        node_ids = [node_id]
        for name in dependencies:
            if not self.resolve_relation(name, node_ids, tasks_per_node):
                logger.warning(
                    "Dependency '%s' cannot be resolved: "
                    "no such task in node '%s'.",
                    name, node_id
                )
                continue

            yield {
                "name": name, "node_id": node_id
            }

    def expand_cross_dependencies(self, tasks_per_node, dependencies):
        """Expands task dependencies on same node.

        :param tasks_per_node: the task per node mapping
        :param dependencies: the list of cross-node dependencies
        """
        if not dependencies:
            return

        for dep in dependencies:
            found_node_ids = self.resolve_relation(
                dep['name'],
                self.role_resolver.resolve(dep['role']),
                tasks_per_node
            )
            if not found_node_ids:
                logger.warning(
                    "Dependency '%s' cannot be resolved: "
                    "no candidates for role '%s'.",
                    dep['name'], dep['role']
                )
                continue

            if dep.get('policy') == consts.POLICY_ANY:
                found_node_ids = [random.choice(found_node_ids)]

            for node_id in found_node_ids:
                yield {
                    'name': dep['name'], "node_id": node_id
                }

    @classmethod
    def resolve_relation(cls, pattern, node_ids, tasks_per_node):
        """Resolves the task relation.

        :param pattern: the pattern to match
        :param node_ids: the ID of nodes where need to search
        :param tasks_per_node: the task per node mapping
        """
        pattern = re.compile(pattern)
        found_node_ids = []
        for node_id in node_ids:
            for task_name in tasks_per_node[node_id]:
                if pattern.match(task_name):
                    found_node_ids.append(node_id)

        return found_node_ids

    @classmethod
    def is_task_based_deployment_allowed(cls, task):
        """Checks that tasks is supported task based deployment.
        :param task: the task instance
        """
        # TODO (make @vsharshov happy)
        return True
        return StrictVersion(task.get('version', '0.0.0')) >= \
            consts.TASK_CROSS_DEPENDENCY
