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

import json
import readline
import sys
import traceback

from nailgun import consts
from nailgun.fuyaql import completion
from nailgun import objects
from nailgun.orchestrator import deployment_serializers
from nailgun import yaql_ext


class FuYaqlContext(object):
    def __init__(self):
        self.cluster = None
        self.node_id = None
        self.task_to = None
        self.task_from = None
        self.state_to = None
        self.state_from = None
        self.yaql_context = yaql_ext.create_context(
            add_serializers=True, add_datadiff=True
        )
        self.yaql_engine = yaql_ext.create_engine()

    def load_cluster(self, cluster_id=None):
        """Load the cluster object.

        :param cluster_id: id of a cluster
        """
        cluster = objects.Cluster.get_by_uid(cluster_id)
        if cluster:
            self.cluster = cluster
            self.node_id = None
            self.task_to = None
            self.task_from = None
            self.state_to = None
            self.state_from = None
            # use the last deployment state by default
            self.set_task_from('last')
            return True
        return False

    def load_state_to(self):
        """Ensure that expected state is loaded."""
        if self.state_to is not None:
            return

        if self.task_to:
            self.state_to = objects.Transaction.get_deployment_info(
                self.task_to
            )
        else:
            assert self.cluster
            deployment_info = deployment_serializers.serialize_for_lcm(
                self.cluster,
                objects.Cluster.get_nodes_not_for_deletion(self.cluster)
            )
            self.state_to = {
                node['uid']: node for node in deployment_info
            }

    def load_state_from(self):
        """Ensure that expected state is loaded."""
        if self.state_from is not None:
            return

        if self.task_from:
            self.state_from = objects.Transaction.get_deployment_info(
                self.task_from
            )
        else:
            self.state_from = {}

    def set_node(self, node_id):
        """Sets the node id."""
        self.load_state_to()
        if node_id in self.state_to:
            self.node_id = node_id
            return True
        return False

    def set_task_to(self, task_id):
        """Sets the task, which is used to get state to."""
        assert self.cluster
        if task_id:
            task = self._get_task(task_id)
            if not task:
                return False
        else:
            task = None

        self.task_to = task
        self.state_to = None
        self.node_id = None
        return True

    def set_task_from(self, task_id):
        """Sets the task, which is used to get state to."""
        assert self.cluster
        if task_id:
            if task_id != 'last':
                task = self._get_task(task_id)
            else:
                task = objects.TransactionCollection.get_last_succeed_run(
                    self.cluster
                )
            if not task:
                return False
        else:
            task = None

        self.task_from = task
        self.state_from = None
        return True

    def get_node(self, new_state=True):
        """Gets the full information about node."""
        assert self.node_id is not None
        if new_state:
            self.load_state_to()
            return self.state_to[self.node_id]
        self.load_state_from()
        return self.state_from.get(self.node_id, {})

    def get_tasks(self):
        query = objects.TransactionCollection.filter_by(
            None,
            cluster_id=self.cluster.id, name=consts.TASK_NAMES.deployment
        )
        query = objects.TransactionCollection.filter_by_not(
            query, deployment_info=None
        )
        return objects.TransactionCollection.order_by(query, 'id')

    @staticmethod
    def get_clusters():
        return objects.ClusterCollection.all()

    def get_nodes(self):
        self.load_state_to()
        for node_id in sorted(self.state_to):
            yield self.state_to[node_id]

    def _get_task(self, task_id):
        """Gets task by id and checks that it belongs to cluster."""
        task = objects.Transaction.get_by_uid(task_id, fail_if_not_found=False)
        if task and task.cluster_id == self.cluster.id:
            return task

    def evaluate(self, expression):
        """Evaluate given YAQL expression

        :param expression: YAQL expression which needed to be evaluated
        :return: result of evaluation as a string
        """
        self.load_state_to()
        self.load_state_from()

        context = self.yaql_context.create_child_context()
        context['$%new'] = self.get_node(True)
        context['$%old'] = self.get_node(False)

        parsed_exp = self.yaql_engine(expression)
        return parsed_exp.evaluate(data=context['$%new'], context=context)


class FuyaqlInterpreter(object):
    COMMANDS = {
        ':show clusters': 'show_clusters',
        ':show cluster': 'show_cluster',
        ':use cluster': 'set_cluster',
        ':show tasks': 'show_tasks',
        ':use task new': 'set_task_to',
        ':use task old': 'set_task_from',
        ':show nodes': 'show_nodes',
        ':show node': 'show_node',
        ':use node': 'set_node',
        ':help': 'show_help'
    }

    def __init__(self, cluster_id=None, node_id=None):
        self.context = FuYaqlContext()
        if cluster_id is not None:
            self.set_cluster(cluster_id)
            if node_id is not None:
                self.set_node(node_id)

    def _check_cluster(self):
        if not self.context.cluster:
            print("Select cluster at first.")
            return False
        return True

    def _check_node(self):
        if not self.context.node_id:
            print("Select node at first.")
            return False
        return True

    @staticmethod
    def print_list(column_names, iterable):
        template = '\t|\t'.join('{%d}' % x for x in range(len(column_names)))
        print(template.format(*column_names))
        print('-'*60)
        for column in iterable:
            print(template.format(*(column.get(x, '-') for x in column_names)))

    @staticmethod
    def print_object(name, properties, obj):
        print(name.title() + ':')
        for p in properties:
            print("\t{0}:\t{1}".format(p, obj.get(p, '-')))

    def show_help(self):
        """Shows this help."""
        for cmd in sorted(self.COMMANDS):
            doc = getattr(self, self.COMMANDS[cmd]).__doc__
            print(cmd, '-', doc)

    def show_clusters(self):
        """Shows all clusters which is available for choose."""
        self.print_list(('id', 'name', 'status'), self.context.get_clusters())

    def show_tasks(self):
        """Shows all tasks which is available for choose."""
        if self._check_cluster():
            self.print_list(('id', 'status'), self.context.get_tasks())

    def show_nodes(self):
        """Shows all tasks which is available for choose."""
        if self._check_cluster():
            self.print_list(
                ('uid', 'status', 'roles'), self.context.get_nodes()
            )

    def show_cluster(self):
        """Shows details of selected cluster."""
        if self.context.cluster:
            self.print_object('cluster', ('id', 'name'), self.context.cluster)
        else:
            print("There is no cluster.")

    def _show_task(self, task):
        if task:
            self.print_object('task', ('id', 'status'), task)
        else:
            print("Please select task at first.")

    def show_task_to(self):
        """Shows details of task, which belongs to new state of cluster."""
        self._show_task(self.context.task_to)

    def show_task_from(self):
        """Shows details of task, which belongs to old state of cluster."""
        self._show_task(self.context.task_from)

    def show_node(self, state='to'):
        """Shows details of selected node."""
        available_states = {'new': True, 'old': False}
        if self.context.node_id:
            try:
                new_state = available_states.get(state, 'new')
            except KeyError:
                print("Please choose state: 'new' or 'old'.")
                return
            return self.context.get_node(new_state)
        else:
            print("Please select node at first.")

    def set_cluster(self, cluster_id):
        """Select the cluster."""
        if not self.context.load_cluster(cluster_id):
            print("Cannot load cluster by id:", cluster_id)

    def set_node(self, node_id):
        """Select the node."""
        if not self.context.set_node(node_id):
            print("There is no node with id:", node_id)

    def set_task_to(self, task_id):
        """Select the task which will belong to state new."""
        if self._check_cluster():
            self.context.set_task_to(task_id)

    def set_task_from(self, task_id):
        """Select the task which will belong to state old."""
        if self._check_cluster():
            self.context.set_task_from(task_id)

    def evaluate_expression(self, exp):
        if self._check_node():
            return self.context.evaluate(exp)

    def execute_command(self, cmdline):
        for cmd in self.COMMANDS:
            if (cmdline.startswith(cmd) and
                    (len(cmdline) == len(cmd) or cmdline[len(cmd)].isspace())):
                break
        else:
            print("Unknown command.")
            print("Please use :help to see list of available commands")
            return

        f = getattr(self, self.COMMANDS[cmd])
        args = cmdline[len(cmd):].split()
        return f(*args) if args else f()

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
                r = None
                if command in (':q', 'exit'):
                    break
                elif command.startswith(':'):  # Check for internal command
                    r = self.execute_command(command)
                else:
                    r = self.evaluate_expression(command)

                if r is not None:
                    print(json.dumps(r, indent=4))
            except Exception as e:
                print("Unexpected error: {0}".format(e))
                traceback.print_exc(sys.stdout)


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
