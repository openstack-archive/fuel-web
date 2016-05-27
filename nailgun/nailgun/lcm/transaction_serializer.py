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

from distutils.version import StrictVersion
import multiprocessing

import six

from nailgun import consts
from nailgun import errors
from nailgun.lcm.task_serializer import TasksSerializersFactory
from nailgun.logger import logger
from nailgun.settings import settings
from nailgun.utils.role_resolver import NameMatchingPolicy


# This class has similar functional with TasksSerializer from task deploy
# but there is no chance to re-use TasksSerializer until bug
# https://bugs.launchpad.net/fuel/+bug/1562292 is not fixed


def _serialize_task_for_node(factory, node_and_task):
    node_id, task = node_and_task
    logger.debug(
        "applying task '%s' for node: %s", node_id, task['id']
    )
    task_serializer = factory.create_serializer(task)
    try:
        serialized = task_serializer.serialize(node_id)
        return node_id, serialized
    except Exception:
        logger.exception("Failed to serialize task %s", task['id'])
        raise


def _initialize_worker(serializers_factory, context):
    globals()['__factory'] = serializers_factory(context)


def _serialize_task_for_node_in_worker(node_and_task):
    return _serialize_task_for_node(globals()['__factory'], node_and_task)


class SingleWorkerConcurrencyPolicy(object):
    def execute(self, context, serializers_factory, tasks):
        factory = serializers_factory(context)
        for node_and_task in tasks:
            yield _serialize_task_for_node(factory, node_and_task)


class MultiProcessingConcurrencyPolicy(object):
    def __init__(self, workers_num):
        self.workers_num = workers_num

    def execute(self, context, serializers_factory, tasks):
        """Executes task serialization in parallel.

        :param context: the transaction context
        :param serializers_factory: the serializers factory
        :param tasks: the tasks to serialize
        :return sequence of serialized tasks
        """
        pool = multiprocessing.Pool(
            processes=self.workers_num,
            initializer=_initialize_worker,
            initargs=(serializers_factory, context)
        )

        try:
            result = pool.imap_unordered(
                _serialize_task_for_node_in_worker, tasks
            )
            for r in result:
                yield r
        except Exception:
            pool.terminate()
            raise
        else:
            pool.close()
        finally:
            pool.join()


def get_concurrency_policy():
    cpu_num = settings.LCM_SERIALIZERS_CONCURRENCY_FACTOR
    if not cpu_num:
        try:
            cpu_num = multiprocessing.cpu_count()
        except NotImplementedError:
            cpu_num = 1

    if cpu_num > 1:
        return MultiProcessingConcurrencyPolicy(cpu_num)
    return SingleWorkerConcurrencyPolicy()


class TransactionSerializer(object):
    """The deploy tasks serializer."""

    serializer_factory_class = TasksSerializersFactory

    min_supported_task_version = StrictVersion(consts.TASK_CROSS_DEPENDENCY)

    unversioned_task_types = (
        consts.ORCHESTRATOR_TASK_TYPES.stage,
        consts.ORCHESTRATOR_TASK_TYPES.skipped
    )

    def __init__(self, context, role_resolver):
        self.role_resolver = role_resolver
        self.context = context
        self.tasks_graph = {}
        self.tasks_dictionary = {}
        self.concurrency_policy = get_concurrency_policy()

    @classmethod
    def serialize(cls, context, tasks, role_resolver):
        """Resolves roles and dependencies for tasks.

        :param context: the deployment context
        :param tasks: the deployment tasks
        :param role_resolver: the nodes role resolver
        :return: the list of serialized task per node
        """
        serializer = cls(context, role_resolver)
        serializer.process_tasks(tasks)
        serializer.resolve_dependencies()
        tasks_graph = serializer.tasks_graph
        for node_id in tasks_graph:
            tasks_graph[node_id] = list(
                six.itervalues(tasks_graph[node_id])
            )
        return serializer.tasks_dictionary, tasks_graph

    @classmethod
    def ensure_task_based_deploy_allowed(cls, task):
        """Raises error if task does not support cross-dependencies.

        :param task: the task instance
        :raises: errors.TaskBaseDeploymentNotAllowed
        """
        if task.get('type') in cls.unversioned_task_types:
            return

        version = StrictVersion(task.get('version', '0.0.0'))
        if version < cls.min_supported_task_version:
            message = (
                "Task '{0}' does not support cross-dependencies.\n"
                "You can enable option 'propagate_task_deploy'"
                "for cluster to use task adaptation mechanism."
                .format(task['id'])
            )
            logger.warning(message)
            if settings.LCM_CHECK_TASK_VERSION:
                raise errors.TaskBaseDeploymentNotAllowed(message)

    def process_tasks(self, tasks):
        """Process all deployment tasks

        :param tasks: the deployment tasks
        :return the mapping tasks per node
        """
        serialized = self.concurrency_policy.execute(
            self.context,
            self.serializer_factory_class,
            self.expand_tasks(tasks)
        )

        for node_and_task in serialized:
            node_id, task = node_and_task
            node_tasks = self.tasks_graph.setdefault(node_id, {})
            # de-duplication the tasks on node
            # since task can be added after expand group need to
            # overwrite if existed task is skipped and new is not skipped.
            if self.need_update_task(node_tasks, task):
                node_tasks[task['id']] = task

        # make sure that null node is present
        self.tasks_graph.setdefault(None, {})

    def expand_tasks(self, tasks):
        groups = []
        tasks_mapping = {}

        for task in tasks:
            if task.get('type') == consts.ORCHESTRATOR_TASK_TYPES.group:
                groups.append(task)
            else:
                self.ensure_task_based_deploy_allowed(task)
                tasks_mapping[task['id']] = task
                for node_id in self.resolve_nodes(task):
                    yield node_id, task

        for task in groups:
            node_ids = self.role_resolver.resolve(
                task.get('roles', task.get('groups'))
            )
            for sub_task_id in task.get('tasks', ()):
                try:
                    sub_task = tasks_mapping[sub_task_id]
                except KeyError:
                    msg = 'Task {0} cannot be resolved'.format(sub_task_id)
                    logger.error(msg)
                    raise errors.InvalidData(msg)
                # if group is not excluded, all task should be run as well
                # otherwise check each task individually
                for node_id in node_ids:
                    yield node_id, sub_task

    def resolve_nodes(self, task):
        if task.get('type') == consts.ORCHESTRATOR_TASK_TYPES.stage:
            # all synchronisation tasks will run on sync node
            return [None]
        # TODO(bgaifullin) remove deprecated groups
        return self.role_resolver.resolve(
            task.get('roles', task.get('groups'))
        )

    def resolve_dependencies(self):
        """Resolves tasks dependencies."""

        for node_id, tasks in six.iteritems(self.tasks_graph):
            for task_id, task in six.iteritems(tasks):
                requires = set(self.expand_dependencies(
                    node_id, task.pop('requires', None)
                ))
                requires.update(self.expand_cross_dependencies(
                    task_id, node_id, task.pop('cross_depends', None)
                ))
                required_for = set(self.expand_dependencies(
                    node_id, task.pop('required_for', None)
                ))
                required_for.update(self.expand_cross_dependencies(
                    task_id, node_id, task.pop('cross_depended_by', None)
                ))
                # render
                if requires:
                    task['requires'] = [
                        dict(six.moves.zip(('name', 'node_id'), r))
                        for r in requires
                    ]
                if required_for:
                    task['required_for'] = [
                        dict(six.moves.zip(('name', 'node_id'), r))
                        for r in required_for
                    ]

    def expand_dependencies(self, node_id, dependencies):
        """Expands task dependencies on same node.

        :param node_id: the ID of target node
        :param dependencies: the list of dependencies on same node
        """
        if not dependencies:
            return

        # need to search dependencies on node and in sync points
        node_ids = [node_id, None]
        for name in dependencies:
            for rel in self.resolve_relation(name, node_ids):
                yield rel

    def expand_cross_dependencies(self, task_id, node_id, dependencies):
        """Expands task dependencies on same node.

        :param task_id: the ID of task
        :param node_id: the ID of target node
        :param dependencies: the list of cross-node dependencies
        """
        if not dependencies:
            return

        for dep in dependencies:
            roles = dep.get('role', consts.TASK_ROLES.all)

            if roles == consts.TASK_ROLES.self:
                node_ids = [node_id]
                excludes = []
            elif roles is None:
                node_ids = [None]
                excludes = []
            else:
                node_ids = self.role_resolver.resolve(
                    roles, dep.get('policy', consts.NODE_RESOLVE_POLICY.all)
                )
                excludes = [(task_id, node_id)]

            relations = self.resolve_relation(dep['name'], node_ids, excludes)
            for rel in relations:
                yield rel

    def resolve_relation(self, name, node_ids, excludes=None):
        """Resolves the task relation.

        :param name: the name of task
        :param node_ids: the ID of nodes where need to search
        :param excludes: the nodes to exclude
        """
        match_policy = NameMatchingPolicy.create(name)
        for node_id in node_ids:
            for task_name in self.tasks_graph.get(node_id, ()):
                if excludes and (task_name, node_id) in excludes:
                    continue
                if match_policy.match(task_name):
                    yield task_name, node_id

    @classmethod
    def need_update_task(cls, tasks, task):
        """Checks that task shall overwrite existed one or should be added.

        :param tasks: the current node tasks
        :param task: the astute task object
        :return True if task is not present or must be overwritten
                otherwise False
        """
        existed_task = tasks.get(task['id'])
        if existed_task is None:
            return True

        if existed_task['type'] == task['type']:
            return False

        return task['type'] != consts.ORCHESTRATOR_TASK_TYPES.skipped
