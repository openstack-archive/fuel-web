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

import json
import logging

import nailgun.fuyaql.completion as completion
from nailgun.fuyaql.f_consts import RESERVED_COMMANDS
from nailgun import objects
from nailgun.orchestrator import deployment_serializers
from nailgun import yaql_ext
import os
import readline
import sys

module_logger = logging.getLogger(__name__)


class Fuyaql(object):
    def __init__(self, logger, cluster_id=None, node_id='master'):
        self.logger = logger
        self.cluster_id = cluster_id,
        self.node_id = node_id

        self.cluster = None
        self.nodes_to_deploy = None

        self.expected_state = None

        self.old_context_task = None
        self.current_state = None
        self.context = None
        self.create_context()

        self.yaql_engine = None

    def get_cluster(self, cluster_id=None):
        """Get cluster from DB

        :param cluster_id: id of a cluster
        :return: SQLAlchemy cluster object
        """
        if not cluster_id:
            cluster_id = self.cluster_id
        try:
            return objects.Cluster.get_by_uid(cluster_id,
                                              fail_if_not_found=True)
        except Exception:
            self.logger.exception("Can't load cluster with id {}".format(
                cluster_id))
            sys.exit(1)

    def populate_nodes_to_deploy(self):
        """Gets nodes which needs to be deployed for this cluster

        Needed for create needed further data in case of user on real
        deployments.
        """
        self.nodes_to_deploy = list(
            objects.Cluster.get_nodes_not_for_deletion(self.cluster).all()
        )
        self.logger.debug('Nodes to deploy are: %s', self.nodes_to_deploy)

    def init_real_expected_state(self):
        """Save expected state based on info from LCM serializer"""
        expected_deployment_info = deployment_serializers.serialize_for_lcm(
            self.cluster,
            self.nodes_to_deploy
        )
        self.expected_state = {node['uid']: node for node in
                               expected_deployment_info}
        self.logger.debug('Expected state is %s', self.expected_state)

    def init_last_successful_task(self):
        """Get last successful deployment info"""
        self.old_context_task = (
            objects.TransactionCollection.get_last_succeed_run(self.cluster))

    def init_current_state(self):
        """Get old context data from last successful deployment info"""
        self.current_state = objects.Transaction.get_deployment_info(
            self.old_context_task) or {}
        self.logger.debug('Current state is: %s', self.current_state)

    def create_context(self):
        """Create main YAQL context"""
        if not self.context:
            main_yaql_context = yaql_ext.create_context(
                add_serializers=True, add_datadiff=True
            )
            self.context = main_yaql_context.create_child_context()

    def update_contexts(self):
        """Set old and new contexts for further evaluation"""
        try:
            self.context['$%new'] = self.expected_state[self.node_id]
        except KeyError:
            self.context['$%new'] = self.expected_state['master']
        try:
            self.context['$%old'] = self.current_state[self.node_id]
        except KeyError:
            self.context['$%old'] = {}

    def create_evaluator(self):
        """Create yaql engine"""
        self.yaql_engine = yaql_ext.create_engine()

    def evaluate(self, yaql_expression):
        """Evaluate given YAQL expression

        :param yaql_expression: YAQL expression which needed to be evaluated
        :type yaql_expression: str
        :return: result of evaluation as a string
        """
        try:
            parsed_exp = self.yaql_engine(yaql_expression)
            self.logger.debug('parsed exp is: %s', parsed_exp)
            res = parsed_exp.evaluate(data=self.context['$%new'],
                                      context=self.context)
            self.logger.debug('Evaluation result is: %s', res)
        except Exception as exc:
            res = '<Evaluation exception caught: {0}>'.format(exc)
            self.logger.exception(res)
        return res

    def create_structure(self):
        """Aggregate internal methods to consist calling"""
        self.cluster = self.get_cluster()
        self.logger.debug('Cluster instance is: %s', self.cluster)
        if not self.cluster:
            return
        self.populate_nodes_to_deploy()
        self.init_real_expected_state()
        self.init_last_successful_task()
        self.init_current_state()
        self.update_contexts()
        self.create_evaluator()

    def parse_command(self, command):
        """Parse internal command taken from user

        :param command: internal fuyaql command
        :type command: str
        :return: tuple with command itself and value of it
        """
        if command.startswith(':show'):
            return command, None
        data = command.split(' ')
        value = data.pop()
        command = ' '.join(data)
        return command, value

    def show_cluster(self):
        """Print cluster data"""
        print('Cluster id is: {}, name is: {}'.format(
              self.cluster.id, self.cluster.name))

    def show_tasks(self):
        """Print tasks data"""
        tasks = [task.id for task in
                 self.cluster.tasks if task.deployment_info]
        print('This cluster has next ids which you can use as context ' +
              'sources: %s' % tasks)
        if self.old_context_task and (self.old_context_task.id in tasks):
            print('Currently task with id %s is used as old context source' %
                  self.old_context_task.id)

    def use_old_context_from_task(self, task_id):
        """Load old context from given cluster task id

        :param task_id: cluster task id
        :type task_id: str
        :return: True if success, False if fails
        """
        tasks = [task for task in self.cluster.tasks if task.deployment_info]
        task = [task for task in tasks if str(task.id) == task_id]
        if not task:
            print("There is no task with id %s, can't switch to it" % task_id)
            return False
        self.old_context_task = task[0]
        self.init_current_state()
        self.update_contexts()
        return True

    def use_new_context_from_task(self, task_id):
        """Load new context from given cluster task id

        :param task_id: cluster task id
        :type task_id: str
        :return: True if success, False if fails
        """
        tasks = [task for task in self.cluster.tasks if task.deployment_info]
        task = next([task for task in tasks if str(task.id) == task_id])
        if not task:
            print("There is no task with id %s, can't switch to it" % task_id)
            return False
        self.expected_state = task.deployment_info
        self.update_contexts()
        return True

    def show_nodes(self):
        """Print cluster nodes data"""
        nodes_ids = {}
        for node in self.cluster.nodes:
            nodes_ids[node.id] = str(', '.join(node.all_roles))
        print('Cluster has nodes with ids: %s' % nodes_ids)

    def show_current_node(self):
        """Print currently used node data"""
        print('Currently used node id is: %s' % self.node_id)

    def use_cluster(self, cluster_id):
        """Start use another cluster instead of current one

        :param cluster_id: id of a new cluster for use
        :type cluster_id: str
        :return: True if success, False if fails
        """
        cluster = self.get_cluster(cluster_id)
        if not cluster:
            print("There is no cluster with id %s, can't switch to it" %
                  cluster_id)
            return False
        self.cluster_id = cluster_id
        self.logger.info("Cluster changed, reset default node id to master")
        self.node_id = 'master'
        self.create_structure()
        return True

    def use_node(self, node_id):
        """Use another node rather than default or given via options

        :param node_id: id of a node for use
        :type node_id: str
        """
        if node_id not in [str(node.id) for node in self.cluster.nodes]:
            print('There is no node with id %s in cluster %s' %
                  (node_id, self.cluster_id))
        self.node_id = node_id
        self.update_contexts()

    def run_internal_command(self, command, value):
        """Run internal command

        Gets instance method name from consts and run it

        :param command: command to run
        :type command: str
        :param value: value to pass to the command
        :type value: str
        :return: True if success, False if fails
        """
        if command not in RESERVED_COMMANDS:
            print('Unknown internal command')
            return False
        if value is not None:
            getattr(self, RESERVED_COMMANDS[command])(value)
        else:
            getattr(self, RESERVED_COMMANDS[command])()
        return True

    def get_console(self):
        """Create a loop for user input"""
        command = True

        while command != 'exit':  # Check for an exit in a loop
            try:
                command = raw_input('fuel-yaql> ').strip()
            except EOFError:
                return
            if not command:
                continue

            if command.startswith(':'):  # Check for internal command
                command, value = self.parse_command(command)
                self.run_internal_command(command, value)
            else:
                result = self.evaluate(command)
                print(json.dumps(result, indent=4))


def lean_contexts(opts):
    """Create lean evaluator from just two contexts

    :param opts: options object
    :type opts: Docopt object
    """
    evaluator = Fuyaql(opts.logger)
    try:
        with open(os.path.expanduser(opts.options['--old']), 'r') as f:
            current_state = json.load(f)
        with open(os.path.expanduser(opts.options['--expected']), 'r') as f:
            expected_state = json.load(f)
    except IOError:
        sys.exit(1)
    evaluator.context['$%new'] = expected_state
    evaluator.context['$%old'] = current_state
    evaluator.create_evaluator()

    expression = opts.options['--expression']
    try:
        parsed_exp = evaluator.yaql_engine(expression)
        parsed_exp.evaluate(data=evaluator.context['$%new'],
                            context=evaluator.context)
        result = 0
    except Exception:
        result = 1
    sys.exit(result)


def main(cluster_id, **kwargs):
    if not cluster_id:
        module_logger.error('Cluster id is required, exiting')
        sys.exit(1)
    # set up command history and completion
    readline.set_completer_delims(r'''`~!@#$%^&*()-=+[{]}\|;'",<>/?''')
    readline.set_completer(completion.FuCompleter(
        RESERVED_COMMANDS.keys()
    ).complete)
    readline.parse_and_bind('tab: complete')
    node_id = kwargs.get('node_id', 'master')
    interpret = Fuyaql(module_logger, cluster_id, node_id)
    interpret.create_structure()
    interpret.get_console()

if __name__ == '__main__':
    module_logger.info(
        "This version of fuel-yaql doesn't designed to be ran as " +
        "independent tool. Please, use manage.py for get a working console")
