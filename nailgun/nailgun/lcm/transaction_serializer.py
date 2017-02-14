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

import datetime
import multiprocessing
import os
from Queue import Queue
import shutil
import tempfile

import distributed
from distutils.version import StrictVersion
import six
import toolz

from nailgun import consts
from nailgun import errors
from nailgun.lcm.task_serializer import Context
from nailgun.lcm.task_serializer import TasksSerializersFactory
from nailgun.logger import logger
from nailgun.settings import settings
from nailgun.utils.resolvers import NameMatchingPolicy


# This class has similar functional with TasksSerializer from task deploy
# but there is no chance to re-use TasksSerializer until bug
# https://bugs.launchpad.net/fuel/+bug/1562292 is not fixed


def _serialize_task_for_node(factory, node_and_task):
    node_id, task = node_and_task
    logger.debug(
        "applying task '%s' for node: %s", task['id'], node_id
    )
    try:
        task_serializer = factory.create_serializer(task)
        serialized = task_serializer.serialize(node_id)
        return node_id, serialized
    except Exception:
        logger.exception(
            "failed to serialize task '%s' for node: %s", task['id'], node_id
        )
        raise


def _initialize_worker(serializers_factory, context):
    globals()['__factory'] = serializers_factory(context)


def _serialize_task_for_node_in_worker(node_and_task_and_err):
    node_and_task, err = node_and_task_and_err

    # NOTE(el): See comment for `wrap_task_iter` method.
    if err:
        raise err

    return _serialize_task_for_node(globals()['__factory'], node_and_task)


class SingleWorkerConcurrencyPolicy(object):
    def execute(self, context, serializers_factory, tasks):
        """Executes task serialization synchronously, task by task.

        :param context: the transaction context
        :param serializers_factory: the serializers factory
        :param tasks: the tasks to serialize
        :return sequence of serialized tasks
        """
        factory = serializers_factory(context)
        return six.moves.map(
            lambda x: _serialize_task_for_node(factory, x),
            tasks
        )


def wrap_task_iter(iterator):
    """Workaround is required to prevent deadlock.

    Due to a bug in core python library [1], if iterator passed
    to imap or imap_unordered raises an exception, it hangs in
    deadlock forever, the issue is fixed in python 2.7.10, but
    upstream repositories have much older version.

    [1] http://bugs.python.org/issue23051
    """
    try:
        for i in iterator:
            yield i, None
    except Exception as e:
        yield (None, None), e


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
                _serialize_task_for_node_in_worker, wrap_task_iter(tasks)
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


def _distributed_serialize_tasks_for_node(formatter_contexts_idx,
                                          node_and_tasks, scattered_data):
    """Remote serialization call for DistributedProcessingPolicy

    Code of the function is copied to the workers and executed there, thus
    we are including all required imports inside the function.

    :param formatter_contexts_idx: dict of formatter contexts with node_id
    value as key
    :param node_and_tasks: list of node_id, task_data tuples
    :param scattered_data: feature object, that points to data copied to
    workers
    :return: [(node_id, serialized), error]
    """

    try:
        factory = TasksSerializersFactory(scattered_data['context'])

        # Restoring settings
        settings.config = scattered_data['settings_config']
        for k in formatter_contexts_idx:
            formatter_contexts_idx[k]['SETTINGS'] = settings

    except Exception as e:
        logger.exception("Distributed serialization failed")
        return [((None, None), e)]

    result = []

    for node_and_task in node_and_tasks:

        node_id = None
        try:
            node_id, task = node_and_task

            logger.debug("Starting distributed node %s task %s serialization",
                         node_id, task['id'])

            formatter_context = formatter_contexts_idx[node_id]

            serializer = factory.create_serializer(task)
            serialized = serializer.serialize(
                node_id, formatter_context=formatter_context)

            logger.debug("Distributed node %s task %s serialization "
                         "result: %s", node_id, task['id'], serialized)

            result.append(((node_id, serialized), None))
        except Exception as e:
            logger.exception("Distributed serialization failed")
            result.append(((node_id, None), e))
            break

    logger.debug("Processed tasks count: %s", len(result))
    return result


class DistributedProcessingPolicy(object):

    def __init__(self):
        self.sent_jobs = Queue()
        self.sent_jobs_count = 0

    def _consume_jobs(self, chunk_size=None):
        """Consumes jobs

        If chunk_size is set function consumes specified number of
        Finished tasks or less if sent_jobs_ids queue became empty.
        If chunk_size is None function consumes jobs until
        sent_jobs_ids queue became empty.
        Jobs with statuses Cancelled, Abandoned, Terminated will be
        resent and their ids added to sent_jobs_ids queue

        :param chunk_size: size of consuming chunk
        :return: generator on job results
        """
        logger.debug("Consuming jobs started")

        jobs_to_consume = []
        while not self.sent_jobs.empty():
            job = self.sent_jobs.get()
            jobs_to_consume.append(job)

            if chunk_size is not None:
                chunk_size -= 1
                if chunk_size <= 0:
                    break

        for ready_job in distributed.as_completed(jobs_to_consume):
            results = ready_job.result()
            self.sent_jobs_count -= 1

            for result in results:
                (node_id, serialized), exc = result
                logger.debug("Got ready task for node %s, serialized: %s, "
                             "error: %s", node_id, serialized, exc)
                if exc is not None:
                    raise exc
                yield node_id, serialized

        logger.debug("Consuming jobs finished")

    def _get_formatter_context(self, task_context, formatter_contexts_idx,
                               node_id):
        try:
            return formatter_contexts_idx[node_id]
        except KeyError:
            pass

        logger.debug("Calculating formatter context for node %s", node_id)
        formatter_context = task_context.get_formatter_context(
            node_id)
        # Settings file is already sent to the workers
        formatter_context.pop('SETTINGS', None)
        formatter_contexts_idx[node_id] = formatter_context

        return formatter_context

    def _upload_nailgun_code(self, job_cluster):
        """Creates zip of current nailgun code and uploads it to workers

        TODO(akislitsky): add workers scope when it will be implemented
        in the distributed library

        :param job_cluster: distributed.Client
        """
        logger.debug("Compressing nailgun code")
        file_dir = os.path.dirname(__file__)
        nailgun_root_dir = os.path.realpath(os.path.join(file_dir, '..', '..'))
        archive = os.path.join(tempfile.gettempdir(), 'nailgun')
        result = shutil.make_archive(archive, 'zip', nailgun_root_dir,
                                     'nailgun')
        logger.debug("Nailgun code saved to: %s", result)

        logger.debug("Uploading nailgun archive %s to workers", result)
        job_cluster.upload_file(result)

    def _scatter_data(self, job_cluster, context, workers):
        logger.debug("Scattering data to workers started")
        shared_data = {'context': context, 'settings_config': settings.config}
        scattered = job_cluster.scatter(shared_data, broadcast=True,
                                        workers=workers)
        # Waiting data is scattered to workers
        distributed.wait(scattered.values())
        logger.debug("Scattering data to workers finished")

        return scattered

    def _get_allowed_nodes_statuses(self, context):
        """Extracts node statuses that allows distributed serialization"""
        common = context.new.get('common', {})
        cluster = common.get('cluster', {})
        logger.debug("Getting allowed nodes statuses to use as serialization "
                     "workers for cluster %s", cluster.get('id'))
        check_fields = {
            'ds_use_ready': consts.NODE_STATUSES.ready,
            'ds_use_provisioned': consts.NODE_STATUSES.provisioned,
            'ds_use_discover': consts.NODE_STATUSES.discover,
            'ds_use_error': consts.NODE_STATUSES.error
        }
        statuses = set()
        for field, node_status in check_fields.items():
            if common.get(field):
                statuses.add(node_status)

        logger.debug("Allowed nodes statuses to use as serialization workers "
                     "for cluster %s are: %s", cluster.get('id'), statuses)
        return statuses

    def _get_allowed_nodes_ips(self, context):
        """Filters online nodes from cluster by their status

        In the cluster settings we select nodes statuses allowed for
        using in the distributed serialization. Accordingly to selected
        statuses nodes are going to be filtered.

        :param context: TransactionContext
        :return: set of allowed nodes ips
        """
        ips = set()
        allowed_statuses = self._get_allowed_nodes_statuses(context)
        for node in six.itervalues(context.new.get('nodes', {})):
            if node.get('status') in allowed_statuses:
                ips.add(node.get('ip'))
        ips.add(settings.MASTER_IP)
        return ips

    def _get_allowed_workers(self, job_cluster, allowed_ips):
        """Calculates workers addresses for distributed serialization

        Only workers that placed on the allowed nodes must be selected
        for the serialization.

        :param job_cluster: distributed.Client
        :param allowed_ips: allowed for serialization nodes ips
        :return: list of workers addresses in format 'ip:port'
        """
        logger.debug("Getting allowed workers")
        workers = {}

        # Worker has address like tcp://ip:port
        info = job_cluster.scheduler_info()
        for worker_addr in six.iterkeys(info['workers']):
            ip_port = worker_addr.split('//')[1]
            ip = ip_port.split(':')[0]
            if ip not in allowed_ips:
                continue
            try:
                pool = workers[ip]
                pool.add(ip_port)
            except KeyError:
                workers[ip] = set([ip_port])

        return list(toolz.itertoolz.concat(six.itervalues(workers)))

    def execute(self, context, _, tasks):
        """Executes task serialization on distributed nodes

        :param context: the transaction context
        :param _: serializers factory
        :param tasks: the tasks to serialize
        :return sequence of serialized tasks
        """
        logger.debug("Performing distributed tasks processing")
        sched_address = '{0}:{1}'.format(settings.MASTER_IP,
                                         settings.LCM_DS_JOB_SHEDULER_PORT)
        job_cluster = distributed.Client(sched_address)

        allowed_ips = self._get_allowed_nodes_ips(context)
        workers = self._get_allowed_workers(job_cluster, allowed_ips)
        logger.debug("Allowed workers list for serialization: %s", workers)
        workers_ips = set([ip_port.split(':')[0] for ip_port in workers])
        logger.debug("Allowed workers ips list for serialization: %s",
                     workers_ips)

        task_context = Context(context)
        formatter_contexts_idx = {}
        workers_num = len(workers)
        max_jobs_in_queue = workers_num * settings.LCM_DS_NODE_LOAD_COEFF
        logger.debug("Max jobs allowed in queue: %s", max_jobs_in_queue)

        start = datetime.datetime.utcnow()
        tasks_count = 0

        try:
            self._upload_nailgun_code(job_cluster)
            scattered = self._scatter_data(job_cluster, context, workers)

            for tasks_chunk in toolz.partition_all(
                    settings.LCM_DS_TASKS_PER_JOB, tasks):

                formatter_contexts_for_tasks = {}

                # Collecting required contexts for tasks
                for task in tasks_chunk:
                    node_id, task_data = task
                    formatter_context = self._get_formatter_context(
                        task_context, formatter_contexts_idx, node_id)
                    if node_id not in formatter_contexts_for_tasks:
                        formatter_contexts_for_tasks[node_id] = \
                            formatter_context

                logger.debug("Submitting job for tasks chunk: %s", tasks_chunk)
                job = job_cluster.submit(
                    _distributed_serialize_tasks_for_node,
                    formatter_contexts_for_tasks,
                    tasks_chunk,
                    scattered,
                    workers=workers_ips
                )

                self.sent_jobs.put(job)
                self.sent_jobs_count += 1

                # We are limit the max number of tasks by the number of nodes
                # which are used in the serialization
                if self.sent_jobs_count >= max_jobs_in_queue:
                    for result in self._consume_jobs(chunk_size=workers_num):
                        tasks_count += 1
                        yield result

            # We have no tasks any more but have unconsumed jobs
            for result in self._consume_jobs():
                tasks_count += 1
                yield result
        finally:
            end = datetime.datetime.utcnow()
            logger.debug("Distributed tasks processing finished. "
                         "Total time: %s. Tasks processed: %s",
                         end - start, tasks_count)
            job_cluster.shutdown()


def is_distributed_processing_enabled(context):
    common = context.new.get('common', {})
    return common.get('serialization_policy') == \
        consts.SERIALIZATION_POLICY.distributed


def get_processing_policy(context):
    if is_distributed_processing_enabled(context):
        return DistributedProcessingPolicy()
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

    def __init__(self, context, resolver):
        self.resolver = resolver
        self.context = context
        self.tasks_graph = {}
        self.tasks_dictionary = {}
        # the list of groups, that contains information about
        # ids of nodes in this group and how many nodes in this group can fail
        # and deployment will not be interrupted
        self.fault_tolerance_groups = []
        self.processing_policy = get_processing_policy(context)

    @classmethod
    def serialize(cls, context, tasks, resolver):
        """Resolves roles and dependencies for tasks.

        :param context: the deployment context
        :param tasks: the deployment tasks
        :param resolver: the nodes tag resolver
        :return: the list of serialized task per node
        """
        serializer = cls(context, resolver)
        serializer.process_tasks(tasks)
        serializer.resolve_dependencies()
        tasks_graph = serializer.tasks_graph
        for node_id in tasks_graph:
            tasks_graph[node_id] = list(
                six.itervalues(tasks_graph[node_id])
            )

        return (
            serializer.tasks_dictionary,
            tasks_graph,
            {'fault_tolerance_groups': serializer.fault_tolerance_groups}
        )

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
        serialized = self.processing_policy.execute(
            self.context,
            self.serializer_factory_class,
            self.expand_tasks(tasks)
        )

        for node_and_task in serialized:
            node_id, task = node_and_task
            node_tasks = self.tasks_graph.setdefault(node_id, {})
            # de-duplication the tasks on node
            # since task can be added after expanding of group need to
            # overwrite task if existed task is skipped and new is not skipped.
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
            node_ids = self.resolver.resolve(
                task.get('tags', task.get('roles', task.get('groups')))
            )
            if not node_ids:
                continue

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

            self.fault_tolerance_groups.append({
                'name': task['id'],
                'node_ids': list(node_ids),
                'fault_tolerance': self.calculate_fault_tolerance(
                    task.get('fault_tolerance'), len(node_ids)
                )
            })

    def resolve_nodes(self, task):
        if task.get('type') == consts.ORCHESTRATOR_TASK_TYPES.stage:
            # all synchronisation tasks will run on sync node
            return [None]
        # TODO(bgaifullin) remove deprecated groups
        return self.resolver.resolve(
            task.get('tags', task.get('roles', task.get('groups')))
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

        for dep in six.moves.filter(None, dependencies):
            roles = dep.get('tags', dep.get('role', consts.TASK_ROLES.all))

            if roles == consts.TASK_ROLES.self:
                node_ids = [node_id]
                excludes = []
            elif roles is None:
                node_ids = [None]
                excludes = []
            else:
                node_ids = self.resolver.resolve(
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

    @classmethod
    def calculate_fault_tolerance(cls, percentage_or_value, total):
        """Calculates actual fault tolerance value.

        :param percentage_or_value: the fault tolerance as percent of nodes
            that can fail or actual number of nodes,
            the negative number means the number of nodes
            which have to deploy successfully.
        :param total: the total number of nodes in group
        :return: the actual number of nodes that can fail
        """
        if percentage_or_value is None:
            # unattainable number
            return total + 1

        if isinstance(percentage_or_value, six.string_types):
            percentage_or_value = percentage_or_value.strip()

        try:
            if (isinstance(percentage_or_value, six.string_types) and
                    percentage_or_value[-1] == '%'):
                value = (int(percentage_or_value[:-1]) * total) // 100
            else:
                value = int(percentage_or_value)

            if value < 0:
                # convert negative value to number of nodes which may fail
                value = max(0, total + value)
            return value
        except ValueError as e:
            logger.error(
                "Failed to handle fault_tolerance: '%s': %s. it is ignored",
                percentage_or_value, e
            )
            # unattainable number
            return total + 1
