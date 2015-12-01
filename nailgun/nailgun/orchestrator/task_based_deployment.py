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
from nailgun.utils.role_resolver import NameMatchPolicy
from nailgun.utils.role_resolver import NullResolver
from nailgun.utils.role_resolver import RoleResolver

from oslo_serialization import jsonutils


class NoopSerializer(StandartConfigRolesHook):
    """Serializes tasks that should be skipped by astute."""
    def should_execute(self):
        return True

    def get_uids(self):
        groups = self.task.get('groups', self.task.get('role'))
        if groups is None:
            # it means that task is not associated with any node
            return [None]
        return self.role_resolver.resolve(groups)

    def serialize(self):
        uids = self.get_uids()
        yield make_noop_task(uids, self.task)


class DeployTaskSerializer(TaskSerializers):
    noop_task_types = (
        consts.ORCHESTRATOR_TASK_TYPES.skipped,
        consts.ORCHESTRATOR_TASK_TYPES.stage
    )

    def __init__(self):
        super(DeployTaskSerializer, self).__init__(
            TaskSerializers.stage_serializers + [CreateVMsOnCompute], []
        )

    def get_stage_serializer(self, task):
        if task.get('type') in self.noop_task_types:
            return NoopSerializer
        return super(DeployTaskSerializer, self).get_stage_serializer(
            task
        )


class TaskProcessor(object):
    """Helper class for deal with task chains."""

    task_attributes_to_copy = (
        'requires', 'cross-depends',
        'required_for', 'cross-depended-by'
    )

    def __init__(self):
        self.origin_task_ids = dict()

    def get_origin(self, task_id):
        """Gets the origin ID of task.

        :param task_id: the id of task
        """
        return self.origin_task_ids.get(task_id, task_id)

    def process_tasks(self, origin_task, serialized_tasks):
        """Processes serialized tasks.

        Adds the valid ID for each task.
        Adds the proper links between serialized tasks in case if one
        puppet task expands to several astute tasks.

        :param origin_task: the origin task object
        :param serialized_tasks: the sequence of serialized tasks
        :return: the sequence of astute tasks
        """

        # TODO (remove expanding puppet tasks from nailgun)

        chain_id = origin_task['id']
        task_iter = iter(serialized_tasks)
        tail = deque(itertools.islice(task_iter, 2), maxlen=2)
        if len(tail) < 2:
            # It is simple case when chain contains only 1 task
            # do nothing
            if len(tail) > 0:
                yield self.patch_task(
                    origin_task, chain_id, tail.pop(),
                    self.task_attributes_to_copy
                )
            return

        # it is chain of tasks, need to properly handle them
        logger.debug("the chain detected: %s", chain_id)
        task = self.patch_first_task_in_chain(origin_task, tail.popleft())
        # the client can modify original task
        # always return the copy
        yield task.copy()

        num = 1
        while True:
            try:
                tail.append(next(task_iter))
            except StopIteration:
                break
            ntask = self.patch_task(
                origin_task, self.get_task_id(chain_id, num), tail.popleft()
            )
            # link current task with previous
            self.link_tasks(task, ntask)
            task = ntask
            yield task.copy()
            num += 1

        ntask = self.patch_last_task_in_chain(origin_task, tail.pop())
        # link this task with previous in chain
        self.link_tasks(task, ntask)
        yield ntask

    def patch_first_task_in_chain(self, origin_task, serialized_task):
        """Patches first astute task in chain.

        The first task shall not contain fields:
        required_for and cross-depended-by

        :param origin_task: the origin puppet task
        :param serialized_task: the serialized task instance
        :returns: the patched serialized task
        """

        task = self.patch_task(
            origin_task,
            self.get_first_task_id(origin_task['id']),
            serialized_task,
            ('requires', 'cross-depends')
        )
        return task

    def patch_last_task_in_chain(self, origin_task, serialized_task):
        """Patches last astute  task in chain.

        The last task shall not contain fields:
        requires and cross-depends

        :param origin_task: the origin puppet task
        :param serialized_task: the serialized task instance
        :returns: the patched serialized task
        """

        task = self.patch_task(
            origin_task,
            self.get_last_task_id(origin_task['id']),
            serialized_task,
            ('required_for', 'cross-depended-by')
        )
        return task

    def patch_task(self, origin_task, task_id, serialized_task, attrs=None):
        """Patches the astute from puppet and serialized task.

        :param origin_task: the origin puppet task
        :param task_id: the ID for task
        :param serialized_task: the serialized task instance
        :param attrs: the attributes that will be copied from puppet task
        :returns: the patched serialized task
        """
        serialized_task['id'] = task_id
        if attrs:
            for attr in attrs:
                try:
                    serialized_task[attr] = origin_task[attr]
                except KeyError:
                    pass
        self.origin_task_ids[task_id] = origin_task['id']
        return serialized_task

    @staticmethod
    def link_tasks(previous, current):
        """Link the previous and current task in chain.

        :param previous: the previous task instance
        :param current: the current task instance
        """

        # in case if uuis is same, that means task will run on same nodes
        if previous.get('uids') == current.get('uids'):
            logger.debug(
                "connect task '%s' with previous in chain '%s'",
                current['id'], previous['id']
            )
            current.setdefault('requires', []).append(previous['id'])
        else:
            # the list of nodes is different, make cross-depends
            logger.debug(
                "cross node dependencies: task '%s', previous task '%s', "
                "nodes: %s",
                current['id'], previous['id'], ', '.join(previous.get('uids', ()))
            )
            requires_ex = current.setdefault('requires_ex', [])
            for node_id in previous.get('uids', ()):
                requires_ex.append(
                    {'name': previous['id'], 'node_id': node_id}
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
    """The deploy tasks serializer."""

    def __init__(self, cluster, nodes):
        """Initializes.
        :param cluster: Cluster instance
        :param nodes: the sequence of nodes for deploy
        """
        self.cluster = cluster
        self.role_resolver = RoleResolver(nodes)
        self.task_serializer = DeployTaskSerializer()
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
        with open("/var/log/nailgun/graph.json", "w") as fd:
            jsonutils.dump(
                serializer.tasks_per_node, fd, indent=4, sort_keys=True
            )

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
            self.ensure_task_based_deployment_allowed(task)
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
                        node_id, task.pop('cross-depended-by', None), True
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

    def resolve_relation(self, name, node_ids, required_for):
        """Resolves the task relation.

        :param name: the name of task
        :param node_ids: the ID of nodes where need to search
        :param required_for: means task from required_for section
        """
        found = False
        match_policy = NameMatchPolicy.create(name)
        for node_id in node_ids:
            applied_tasks = set()
            for task_name in self.tasks_per_node[node_id]:
                if task_name == name:
                    # the simple case when name of current task
                    # is exact math to name of task that is search
                    found = True
                    yield {"name": task_name, "node_id": node_id}
                    continue

                # at first get the original task name, actual
                # when current task is part of chain
                original_task = self.task_processor.get_origin(task_name)
                if original_task in applied_tasks or \
                        not match_policy.match(original_task):
                    continue

                found = True
                applied_tasks.add(original_task)
                if original_task is not task_name:
                    if required_for:
                        task_name_gen = self.task_processor.get_first_task_id
                    else:
                        task_name_gen = self.task_processor.get_last_task_id
                    task_name = task_name_gen(original_task)

                yield {"name": task_name, "node_id": node_id}

        if not found:
            logger.warning(
                "Dependency '%s' cannot be resolved: "
                "no candidates in nodes '%s'.",
                name, ", ".join(six.moves.map(str, node_ids))
            )

    @classmethod
    def ensure_task_based_deployment_allowed(cls, task):
        """Raises error if task is supported task based deployment.
        :param task: the task instance
        """
        return
        task_version = StrictVersion(task.get('version', '0.0.0'))
        if task_version < consts.TASK_CROSS_DEPENDENCY:
            raise errors.TaskBaseDeploymentNotAllowed
