#!/usr/bin/env python
#
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

"""Fuel YAQL real-time console.
Allow fast and easy test your YAQL expressions on live cluster."""
from __future__ import print_function

import inspect
import json
import readline
import sys
import traceback

from nailgun import consts
from nailgun.fuyaql import completion
from nailgun.logger import logger
from nailgun import objects
from nailgun.orchestrator import deployment_serializers
from nailgun.utils import uniondict
from nailgun import yaql_ext


logger.disabled = True


class FuYaqlController(object):
    CURRENT = 0
    EXPECTED = 1

    def __init__(self):
        self._cluster = None
        self._node_id = None
        self._tasks = [None, None]
        self._infos = [None, None]
        self._yaql_context = yaql_ext.create_context(
            add_serializers=True, add_datadiff=True, add_extensions=True
        )
        self._yaql_engine = yaql_ext.create_engine()

    @property
    def cluster(self):
        return self._cluster

    @property
    def node_id(self):
        return self._node_id

    @property
    def selected_tasks(self):
        return self._tasks

    def set_cluster(self, cluster_id=None):
        """Load the cluster object.

        :param cluster_id: id of a cluster
        """
        cluster = objects.Cluster.get_by_uid(
            cluster_id, fail_if_not_found=False
        )
        if cluster:
            self._cluster = cluster
            self._set_task(self.EXPECTED, None)
            self._set_task(
                self.CURRENT,
                objects.TransactionCollection.get_last_succeed_run(cluster)
            )
            return True
        return False

    def set_task(self, state, task_id=None):
        """Sets the task, which is used to get new state."""
        assert self._cluster
        task = self._get_task(task_id)
        if task is not False:
            self._set_task(state, task)
            return True
        return False

    def set_node(self, node_id):
        """Sets the node id."""
        info = self._get_info(self.EXPECTED)
        if node_id in info:
            self._node_id = node_id
            return True
        return False

    def get_node(self):
        """Gets the full information about node."""
        assert self._node_id is not None
        return self._get_info(self.EXPECTED)[self._node_id]

    @staticmethod
    def get_clusters():
        """Gets list of all clusters."""
        return objects.ClusterCollection.order_by(
            objects.ClusterCollection.all(),
            'id'
        )

    def get_tasks(self):
        """Gets all deployment tasks for current cluster."""
        assert self.cluster
        query = objects.TransactionCollection.filter_by(
            None,
            cluster_id=self.cluster.id, name=consts.TASK_NAMES.deployment
        )
        query = objects.TransactionCollection.filter_by_not(
            query, deployment_info=None
        )
        return objects.TransactionCollection.order_by(query, 'id')

    def get_nodes(self):
        info = self._get_info(self.EXPECTED)
        for node_id in sorted(info):
            yield info[node_id]

    def evaluate(self, expression):
        """Evaluate given YAQL expression

        :param expression: YAQL expression which needed to be evaluated
        :return: result of evaluation as a string
        """
        assert self.cluster
        assert self.node_id
        context = self._yaql_context.create_child_context()
        context['$%new'] = self._get_info(self.EXPECTED)[self._node_id]
        context['$%old'] = self._get_info(self.CURRENT).get(self._node_id, {})

        parsed_exp = self._yaql_engine(expression)
        return parsed_exp.evaluate(data=context['$%new'], context=context)

    def _get_task(self, task_id):
        """Gets task by id and checks that it belongs to cluster."""
        if not task_id:
            return None
        task = objects.Transaction.get_by_uid(task_id, fail_if_not_found=False)
        if task and task.cluster_id == self.cluster.id:
            return task
        return False

    def _set_task(self, state, task):
        self._tasks[state] = task
        self._set_info(
            state,
            objects.Transaction.get_deployment_info(task)
        )

    def _set_info(self, state, info):
        if state == self.EXPECTED:
            self._node_id = None
            if not info:
                info = deployment_serializers.serialize_for_lcm(
                    self._cluster,
                    objects.Cluster.get_nodes_not_for_deletion(self._cluster)
                )
                # TODO(bgaifullin) serializer should return nodes as dict
                info['nodes'] = {n['uid']: n for n in info['nodes']}

        if info:
            common = info['common']
            nodes = info['nodes']
            info = {n: uniondict.UnionDict(common, nodes[n]) for n in nodes}
        else:
            info = {}

        self._infos[state] = info

    def _get_info(self, state):
        return self._infos[state]


class FuyaqlInterpreter(object):
    COMMANDS = {
        ':show clusters': 'show_clusters',
        ':show cluster': 'show_cluster',
        ':use cluster': 'set_cluster',
        ':show tasks': 'show_tasks',
        ':use task2': 'set_task2',
        ':use task1': 'set_task1',
        ':show nodes': 'show_nodes',
        ':show node': 'show_node',
        ':use node': 'set_node',
        ':help': 'show_help',
        ':exit': 'shutdown',
        ':q': 'shutdown',
    }

    def __init__(self, cluster_id=None, node_id=None, controller=None):
        self.controller = controller or FuYaqlController()
        if cluster_id is not None:
            self.set_cluster(cluster_id)
            if node_id is not None:
                self.set_node(node_id)

    def show_help(self):
        """Shows this help."""
        for cmd in sorted(self.COMMANDS):
            doc = getattr(self, self.COMMANDS[cmd]).__doc__
            print(cmd, '-', doc)

    def show_clusters(self):
        """Shows all clusters which is available for choose."""
        cluster_ids = [
            self.controller.cluster and self.controller.cluster['id']
        ]
        self.print_list(
            ('id', 'name', 'status'), self.controller.get_clusters(),
            lambda x: cluster_ids.index(x['id'])
        )

    def show_tasks(self):
        """Shows all tasks which is available for choose."""
        task_ids = [
            t and t['id'] for t in self.controller.selected_tasks
        ]

        if self._check_cluster():
            self.print_list(
                ('id', 'status'), self.controller.get_tasks(),
                lambda x: task_ids.index(x['id'])
            )

    def show_nodes(self):
        """Shows all tasks which is available for choose."""
        node_ids = [self.controller.node_id]

        if self._check_cluster():
            self.print_list(
                ('uid', 'status', 'roles'), self.controller.get_nodes(),
                lambda x: node_ids.index(x.get('uid'))
            )

    def show_cluster(self):
        """Shows details of selected cluster."""
        if self.controller.cluster:
            self.print_object(
                'cluster', ('id', 'name', 'status'), self.controller.cluster
            )
        else:
            print("There is no cluster.")

    def show_task2(self):
        """Shows details of task, which belongs to new state of cluster."""
        self._show_task(self.controller.EXPECTED)

    def show_task1(self):
        """Shows details of task, which belongs to old state of cluster."""
        self._show_task(self.controller.CURRENT)

    def show_node(self):
        """Shows details of selected node."""
        if self.controller.node_id:
            self.print_object(
                'node',
                ('uid', 'status', 'roles'),
                self.controller.get_node()
            )
        else:
            print("Please select node at first.")

    def set_cluster(self, cluster_id):
        """Select the cluster."""
        if not self.controller.set_cluster(cluster_id):
            print("There is no cluster with id:", cluster_id)

    def set_node(self, node_id):
        """Select the node."""
        if self._check_cluster():
            if not self.controller.set_node(node_id):
                print("There is no node with id:", node_id)

    def set_task2(self, task_id):
        """Select the task which will belong to state new."""
        self._set_task(self.controller.EXPECTED, task_id)

    def set_task1(self, task_id):
        """Select the task which will belong to state old."""
        self._set_task(self.controller.CURRENT, task_id)

    def evaluate_expression(self, exp):
        if self._check_node():
            return self.controller.evaluate(exp)

    def execute_command(self, cmdline):
        for cmd in self.COMMANDS:
            if (cmdline.startswith(cmd) and
                    (len(cmdline) == len(cmd) or cmdline[len(cmd)].isspace())):
                break
        else:
            print("Unknown command:", cmdline)
            print("Please use :help to see list of available commands")
            return

        f = getattr(self, self.COMMANDS[cmd])
        args = cmdline[len(cmd):].split()
        try:
            inspect.getcallargs(f, *args)
        except (ValueError, TypeError):
            print("Not enough arguments for a command were given.")
            return

        return f(*args)

    @staticmethod
    def shutdown():
        """Exits."""
        sys.exit(0)

    def run_loop(self):
        """Create a loop for user input"""
        while True:
            try:
                command = raw_input('fuel-yaql> ').strip()
            except EOFError:
                return
            if not command:
                continue

            try:
                if command.startswith(':'):  # Check for internal command
                    r = self.execute_command(command)
                else:
                    r = self.evaluate_expression(command)

                if isinstance(r, (list, dict)):
                    print(json.dumps(r, indent=4))
                elif r is not None:
                    print(r)

            except Exception as e:
                print("Unexpected error: {0}".format(e))
                traceback.print_exc(sys.stdout)

    def _show_task(self, state):
        task = self.controller.selected_tasks[state]
        if task:
            self.print_object('task', ('id', 'status'), task)
        else:
            print("Please select task at first.")

    def _set_task(self, state, task_id):
        if self._check_cluster():
            next_state = (state + 1) % len(self.controller.selected_tasks)
            next_task = self.controller.selected_tasks[next_state]
            task_id = int(task_id or 0)
            if task_id and next_task:
                if next_state > state and task_id > next_task['id']:
                    print("The task, which belongs to state old cannot be"
                          " under than task which belongs to state new.")
                    return
                elif next_state < state and task_id < next_task['id']:
                    print("The task, which belongs to state new cannot be"
                          " older than task which belongs to state old.")
                    return
            self.controller.set_task(state, task_id)

    def _check_cluster(self):
        if self.controller.cluster is None:
            print("Select cluster at first.")
            return False
        return True

    def _check_node(self):
        if self.controller.node_id is None:
            print("Select node at first.")
            return False
        return True

    @staticmethod
    def print_list(column_names, iterable, get_selected_index=None):
        template = '\t|\t'.join('{%d}' % x for x in range(len(column_names)))
        print(template.format(*column_names))
        print('-' * (sum(len(x) + 5 for x in column_names)))
        for column in iterable:
            if get_selected_index is not None:
                try:
                    print('*' * (get_selected_index(column) + 1), end=' ')
                except ValueError:
                    pass
            print(template.format(*(column.get(x, '-') for x in column_names)))

    @staticmethod
    def print_object(name, properties, obj):
        print(name.title() + ':')
        for p in properties:
            print("\t{0}:\t{1}".format(p, obj.get(p, '-')))


def main(cluster_id=None, node_id=None):
    # set up command history and completion
    readline.set_completer_delims(r'''`~!@#$%^&*()-=+[{]}\|;'",<>/?''')
    readline.set_completer(completion.FuCompleter(
        list(FuyaqlInterpreter.COMMANDS)
    ).complete)
    readline.parse_and_bind('tab: complete')
    interpret = FuyaqlInterpreter(cluster_id, node_id)
    interpret.run_loop()

if __name__ == '__main__':
    main()
