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
import functools
import itertools

import six

from nailgun import errors


class TaskInheritanceProcessor(object):

    def merge(self, linearizations):
        """Merges linearizations accordingly C3 algorithm

        :param linearizations: collection of linearizations
        :return: linearized tasks hierarchy
        """

        result = []
        lins = linearizations
        while True:
            lins = [lin for lin in lins if lin]
            if not lins:
                return result

            for lin in lins:
                if not lin:
                    continue
                head = lin[0]
                if not any(head in l[1:] for l in lins):
                    break
            else:
                raise errors.LinearizationImpossible()

            result.append(head)
            for lin in lins:
                if lin[0] == head:
                    del lin[0]

        return result

    def linearize(self, tasks_mapping, linearized_tasks, task_id):
        """Linearizes tasks by C3 linearization algorithm.

        If linearization is impossible

        :param tasks_mapping: tasks indexed by task.id
        :param linearized_tasks: linearized tasks cache
        :param task_id: task identifier
        :return: list of task parents
        :raises: WrongTasksHierarchy if linearization can't be done
        """

        # TODO(akislitsky) implement cycles detection
        task = tasks_mapping.get(task_id)
        if task is None:
            raise errors.TaskNotFound(task_id)
        parents = copy.copy(task.get('inherits'))
        if not parents:
            linearized_tasks[task_id] = [task['id']]
            return [task['id']]
        elif task_id in linearized_tasks:
            return copy.copy(linearized_tasks[task_id])
        else:
            linearizer = functools.partial(self.linearize, tasks_mapping,
                                           linearized_tasks)
            result = [task_id] + self.merge(
                itertools.chain(
                    six.moves.map(linearizer, parents),
                    [parents]
                )
            )
            linearized_tasks[task_id] = result
            return result

    def process(self, tasks):
        """Constructs inherited tasks.

        Task inheritance order is calculated by C3 lineariaztion  algorithm.
        Inherited tasks will be updated in the tasks collection.

        :param tasks: collection of tasks to be processed
        """
        tasks_mapping = dict()
        child_tasks = []
        for task in tasks:
            if task.get('inherits'):
                child_tasks.append(task['id'])
            tasks_mapping[task['id']] = task

        linearized_tasks = {}
        for task_id in child_tasks:
            try:
                self.linearize(tasks_mapping, linearized_tasks, task_id)
            except errors.LinearizationImpossible:
                raise errors.WrongTasksHierarchy(task)

        for task_id, tasks_chain in six.iteritems(linearized_tasks):
            result = {}
            # child type always present in the tasks_chain as the first element
            for task_id in reversed(tasks_chain):
                task_data = tasks_mapping[task_id]
                if 'type' in task_data and 'type' in result and \
                        result['type'] != task_data['type']:
                    raise errors.DifferentTasksTypesInheritance(
                        task_data, result['type'])
                result.update(task_data)

            # Updating child task value
            tasks_mapping[task_id].update(result)
