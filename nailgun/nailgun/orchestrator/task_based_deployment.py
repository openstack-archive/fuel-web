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
from collections import deque
from copy import deepcopy
from distutils.version import StrictVersion
import itertools

import six

from nailgun import consts
from nailgun.errors import errors
from nailgun.logger import logger
from nailgun.orchestrator.tasks_serializer import CreateVMsOnCompute
from nailgun.orchestrator.tasks_serializer import StandartConfigRolesHook
from nailgun.orchestrator.tasks_serializer import TaskSerializers
from nailgun.orchestrator.tasks_templates import make_noop_task
from nailgun.utils.role_resolver import compile_strict_pattern
from nailgun.utils.role_resolver import NullResolver
from nailgun.utils.role_resolver import PatternBasedRoleResolver

import datetime
from oslo_serialization import jsonutils


class NoopSerializer(StandartConfigRolesHook):
    def should_execute(self):
        return True

    def serialize(self):
        uids = self.get_uids() or [None]
        yield make_noop_task(uids, self.task)


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


class TaskProcessor(object):
    """Helper class for deal with task chains."""
    task_attributes_to_copy = (
        'requires', 'required_for',
        'cross-depends', 'cross-depends-for'
    )

    def __init__(self):
        self.aliases = dict()

    def resolve_alias(self, task_id):
        """Checks that task is chain of tasks.

        :param task_id: the id of task
        :return: True if task is chain of tasks, otherwise False
        """
        return self.aliases.get(task_id, task_id)

    def process_tasks(self, origin_task, serialized_tasks):
        """Processes serialized tasks.

        Added proper id for each tasks.

        :param origin_task: the origin task object
        :param serialized_tasks: the sequence of serialized tasks
        :return: the sequence of astute tasks
        """

        # TODO (remove expanding puppet tasks from nailgun)

        chain_id = origin_task['id']
        task_iter = iter(serialized_tasks)
        tail = deque(itertools.islice(task_iter, 2), maxlen=2)
        if len(tail) < 2:
            if len(tail) > 0:
                yield self.make_task(origin_task, chain_id, tail.pop())
            return

        logger.debug("the chain detected: %s", chain_id)
        task = self.make_task(
            origin_task, self.get_first_task_id(chain_id), tail.popleft()
        )
        # remove required_for from begin of chain
        task.pop('required_for', None)
        task.pop('cross-depends-for', None)
        yield task.copy()

        num = 1
        while True:
            try:
                tail.append(next(task_iter))
            except StopIteration:
                break
            ntask = self.make_task(
                origin_task, self.get_task_id(chain_id, num),
                tail.popleft(), ()
            )
            self.add_requires(task, ntask)
            task = ntask
            yield task.copy()
            num += 1

        ntask = self.make_task(
            origin_task, self.get_last_task_id(chain_id), tail.pop()
        )
        ntask.pop('cross-depends-for', None)
        self.add_requires(task, ntask)
        yield ntask

    def make_task(self, origin_task, task_id, serialized_task, attrs=None):
        serialized_task['id'] = task_id
        if attrs is None:
            attrs = self.task_attributes_to_copy

        for attr in attrs:
            try:
                serialized_task[attr] = origin_task[attr]
            except KeyError:
                pass
        self.aliases[task_id] = origin_task['id']
        return serialized_task

    @staticmethod
    def add_requires(task, ntask):
        if ntask.get('uids') == task.get('uids'):
            logger.debug(
                "connect task '%s' with previous in chain '%s'",
                ntask['id'], task['id']
            )
            ntask.setdefault('requires', []).append(task['id'])
        else:
            logger.debug(
                "cross node dependencies: task '%s', previous task '%s', "
                "nodes: %s",
                ntask['id'], task['id'], ', '.join(task.get('uids', ()))
            )
            requires_ex = ntask.setdefault('requires_ex', [])
            for node_id in task.get('uids', ()):
                requires_ex.append(
                    {'name': task['id'], 'node_id': node_id}
                )

    @staticmethod
    def get_task_id(chain_name, num):
        return "{0}#{1}".format(chain_name, num)

    @staticmethod
    def get_first_task_id(chain_name):
        return chain_name + "_start"

    @staticmethod
    def get_last_task_id(chain_name):
        return chain_name + "_end"


class TasksSerializer(object):
    def __init__(self, cluster, nodes):
        self.cluster = cluster
        self.role_resolver = PatternBasedRoleResolver(nodes)
        self.task_serializer = DeploymentTaskSerializer()
        self.task_processor = TaskProcessor()
        self.tasks_per_node = defaultdict(dict)

    @classmethod
    def serialize(cls, cluster, nodes, tasks):
        """Resolves roles and dependencies for tasks.

        :param cluster: the cluster instance
        :param nodes: the list of nodes
        :param tasks: the list of tasks
        :return: the list of serialized task per node
        """
        serializer = cls(cluster, nodes)
        serializer.resolve_nodes(tasks, nodes)
        serializer.resolve_dependencies()

        # REMOVE ME
        with open("/var/tmp/nailgun-graph-%s.json" % datetime.datetime.now(), "w") as debug:
            jsonutils.dump(serializer.tasks_per_node, debug, indent=4)

        return dict(
            (k, list(six.itervalues(v)))
            for k, v in six.iteritems(serializer.tasks_per_node)
        )

    def resolve_nodes(self, tasks, nodes):
        """Resolves node roles in tasks.

        :param tasks: the deployment tasks
        :param nodes: the list of nodes to deploy
        :return the mapping tasks per node
        """

        tasks_mapping = dict()
        tasks_groups = defaultdict(set)

        for task in tasks:
            if not self.is_task_based_deployment_allowed(task):
                raise errors.TaskBaseDeploymentNotAllowed

            if task.get('type') == consts.ORCHESTRATOR_TASK_TYPES.group:
                tasks_for_role = task.get('tasks')
                if tasks_for_role:
                    tasks_groups[tuple(task.get('role', ()))].update(
                        tasks_for_role
                    )
                continue
            tasks_mapping[task['id']] = task
            self.process_task(task, nodes, lambda _: self.role_resolver)

        self.expand_tasks(tasks_groups, tasks_mapping)

    def process_task(self, task, nodes, resolver_factory):
        """Processes one task one nodes of cluster.

        :param task: the task instance
        :param nodes: the list of nodes
        :param resolver_factory: the factory creates role-resolver
        """

        serializer_factory = self.task_serializer.get_stage_serializer(
            task
        )
        task_serializer = serializer_factory(
            task, self.cluster, nodes, roles_resolver=resolver_factory(nodes)
        )
        skipped = task.get('skipped') or not task_serializer.should_execute()
        for astute_task in self.task_processor.process_tasks(
                task, task_serializer.serialize()):
            # all skipped task shall have type skipped
            if skipped:
                astute_task['type'] = \
                    consts.ORCHESTRATOR_TASK_TYPES.skipped

            for node_id in astute_task.pop('uids', ()):
                node_tasks = self.tasks_per_node[node_id]
                # de-duplication the tasks on node
                if astute_task['id'] in node_tasks:
                    continue
                node_tasks[astute_task['id']] = deepcopy(astute_task)

    def resolve_dependencies(self):
        """Resolves tasks dependencies."""

        for node_id, tasks in six.iteritems(self.tasks_per_node):
            for task in six.itervalues(tasks):
                task['requires'] = list(
                    self.expand_dependencies(
                        node_id, task.get('requires'), False
                    )
                )
                task['required_for'] = list(
                    self.expand_dependencies(
                        node_id, task.get('required_for'), True
                    )
                )
                task['requires'].extend(
                    self.expand_cross_dependencies(
                        node_id, task.pop('cross-depends', None), False
                    )
                )

                task['required_for'].extend(
                    self.expand_cross_dependencies(
                        node_id, task.pop('cross-depends-for', None), True
                    )
                )
                task['requires'].extend(task.pop('requires_ex', ()))
                task['required_for'].extend(task.pop('required_for_ex', ()))

    def expand_tasks(self, tasks_per_role, task_mapping):
        """Expand ids of tasks.

        :param tasks_per_role: the set of tasks per role
        :param task_mapping: the mapping task id to task object
        """
        for roles, task_ids in six.iteritems(tasks_per_role):
            for task_id in task_ids:
                try:
                    task = task_mapping[task_id]
                except KeyError:
                    raise errors.InvalidData(
                        'Task %s cannot be resolved', task_id
                    )

                for node_id in self.role_resolver.resolve(roles):
                    self.process_task(task, [node_id], NullResolver)

    def expand_dependencies(self, node_id, dependencies, required_for):
        """Expands task dependencies on same node.

        :param node_id: the ID of target node
        :param dependencies: the list of dependencies on same node
        :param required_for: means task from required_for section
        """
        if not dependencies:
            return

        # need to search dependencies on node and in sync points
        node_ids = [node_id, None]
        for name in dependencies:
            for rel in self.resolve_relation(name, node_ids, required_for):
                yield rel

    def expand_cross_dependencies(self, node_id, dependencies, required_for):
        """Expands task dependencies on same node.

        :param node_id: the ID of target node
        :param dependencies: the list of cross-node dependencies
        :param required_for: means task from required_for section
        """
        if not dependencies:
            return

        for dep in dependencies:
            roles = dep.get('role', consts.ALL_ROLES)

            if roles == consts.ROLE_SELF_NODE:
                node_ids = [node_id]
            else:
                node_ids = self.role_resolver.resolve(
                    roles, dep.get('policy')
                )
            relations = self.resolve_relation(
                dep['name'], node_ids, required_for
            )
            for rel in relations:
                yield rel

    def resolve_relation(self, pattern, node_ids, required_for):
        """Resolves the task relation.

        :param pattern: the pattern to match
        :param node_ids: the ID of nodes where need to search
        :param required_for: means task from required_for section
        """
        found = False
        pattern_re = compile_strict_pattern(pattern)
        for node_id in node_ids:
            seen_tasks = set()
            for task_name in self.tasks_per_node[node_id]:
                original_task = self.task_processor.resolve_alias(task_name)
                if pattern_re.match(original_task):
                    if original_task in seen_tasks:
                        continue
                    seen_tasks.add(original_task)
                    if original_task is not task_name:
                        if required_for:
                            task_name = self.task_processor.get_first_task_id(
                                original_task
                            )
                        else:
                            task_name = self.task_processor.get_last_task_id(
                                original_task
                            )
                    yield {"name": task_name, "node_id": node_id}
                    found = True
                elif pattern == task_name:
                    yield {"name": task_name, "node_id": node_id}
                    found = True

        if not found:
            logger.warning(
                "Dependency '%s' cannot be resolved: "
                "no candidates in nodes '%s'.",
                pattern, ", ".join(six.moves.map(str, node_ids))
            )

    @classmethod
    def is_task_based_deployment_allowed(cls, task):
        """Checks that tasks is supported task based deployment.
        :param task: the task instance
        """
        # TODO (make @vsharshov happy)
        return True
        return StrictVersion(task.get('version', '0.0.0')) >= \
            consts.TASK_CROSS_DEPENDENCY
