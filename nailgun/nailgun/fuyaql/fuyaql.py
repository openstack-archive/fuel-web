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
import os
import readline
import sys

import nailgun.fuyaql.completion as completion
from nailgun.fuyaql.f_consts import RESERVED_COMMANDS
from nailgun import objects
from nailgun.orchestrator import deployment_serializers
from nailgun import yaql_ext

module_logger = logging.getLogger(__name__)
if not [_ for _ in (module_logger.handlers + module_logger.parent.handlers) if
        isinstance(_, logging.StreamHandler)]:
    module_logger.addHandler(logging.StreamHandler())


class Fuyaql(object):
    def __init__(self, logger, cluster_id=None, node_id='master'):
        self.logger = logger
        self.cluster_id = cluster_id,
        self.cluster = self.get_cluster(cluster_id)

        self.node_id = node_id
        self.nodes_to_deploy = None

        self.expected_state = None

        self.old_context_task = self.get_last_successful_task()
        self.previous_state = None
        self.context = None
        self.main_yaql_context = yaql_ext.create_context(
            add_serializers=True, add_datadiff=True)
        self.create_context()

        self.yaql_engine = yaql_ext.create_engine()

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
        except Exception as exc:
            self.logger.exception("Can't load cluster with id {}: {}".format(
                cluster_id, exc))
        return None

    def populate_nodes_to_deploy(self):
        """Gets nodes which needs to be deployed for this cluster

        Needed for create further data in case of user on real deployments.
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

    def get_last_successful_task(self):
        """Get last successful deployment info

        :return: old context task if any, other way return None
        """
        if self.cluster:
            return objects.TransactionCollection.get_last_succeed_run(
                self.cluster)
        return None

    def init_previous_state(self):
        """Get old context data from deployment info"""
        self.previous_state = objects.Transaction.get_deployment_info(
            self.old_context_task) or {}
        self.logger.debug('Current state is: %s', self.previous_state)

    def create_context(self):
        """Create main YAQL context"""
        self.context = self.main_yaql_context.create_child_context()

    def update_contexts(self):
        """Set old and new contexts for further evaluation"""
        try:
            self.context['$%new'] = self.expected_state[self.node_id]
        except KeyError:
            self.context['$%new'] = {}
        try:
            self.context['$%old'] = self.previous_state[self.node_id]
        except KeyError:
            self.context['$%old'] = {}

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
        self.logger.debug('Cluster instance is: %s', self.cluster)
        if not self.cluster:
            return
        self.populate_nodes_to_deploy()
        self.init_real_expected_state()
        self.init_previous_state()
        self.update_contexts()

    def show_cluster(self):
        """Print cluster data"""
        if self.cluster:
            print('Cluster id is: {}, name is: {}'.format(
                  self.cluster.id, self.cluster.name))
        else:
            print('No cluster loaded')

    def show_tasks(self):
        """Print tasks data"""
        if not self.cluster:
            print('No cluster loaded, so there are no tasks in it')
            return
        tasks = [task.id for task in
                 self.cluster.tasks if task.deployment_info]
        print('This cluster has next ids which you can use as context ' +
              'sources: %s' % tasks)
        if self.old_context_task and (self.old_context_task.id in tasks):
            print('Currently task with id %s is used as old context source' %
                  self.old_context_task.id)

    def check_cluster(self):
        """Checks if there is a loaded cluster

        :return: True if cluster loaded, False other way
        """
        if not self.cluster:
            print("Please select cluster at first")
            return False
        return True

    def load_previous_context(self, task_id=None):
        """Load old context from given cluster task id

        :param task_id: cluster task id
        :type task_id: str
        :return: True if success, False if fails
        """
        if not self.check_cluster():
            return False
        if task_id is None:
            task = self.get_last_successful_task()
        else:
            task = objects.Transaction.get_by_uid(task_id)
            if not task or task.cluster_id != self.cluster.id:
                print("There is no task with id {} in current cluster".format(
                      task_id))
                return False
        self.old_context_task = task[0]
        self.init_previous_state()
        self.update_contexts()
        return True

    def load_current_context(self, task_id=None):
        """Load new context from given cluster task id

        :param task_id: cluster task id
        :type task_id: str
        :return: True if success, False if fails
        """
        if not self.check_cluster():
            return False
        if task_id is None:
            self.populate_nodes_to_deploy()
            self.init_real_expected_state()
        else:
            task = objects.Transaction.get_by_uid(task_id)
            if not task or task.cluster_id != self.cluster.id:
                print("There is no task with id {} in current cluster".format(
                      task_id))
                return False
            self.expected_state = task.deployment_info
        self.update_contexts()
        return True

    def show_nodes(self):
        """Print cluster nodes data"""
        if not self.expected_state:
            print("Please load current context first")
        else:
            for uid in sorted(self.expected_state):
                if uid != 'master':
                    print("uid: {}; roles: {}".format(
                        uid, self.expected_state[uid]['roles']))

    def show_current_node(self):
        """Print currently used node data"""
        print(json.dumps(self.expected_state[self.node_id]))

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
        if not self.expected_state:
            print("Please load current state first")
        else:
            if node_id not in self.previous_state:
                print('There is no node with id {} in previous state'.format(
                      node_id))
            self.node_id = node_id
            self.update_contexts()

    def run_internal_command(self, command):
        """Run internal command

        Gets instance method name from consts and run it

        :param command: command to run
        :type command: str
        :return: True if success, False if fails
        """
        for cmd in RESERVED_COMMANDS:
            if command.startswith(cmd):
                command_name = cmd
                value = command[len(cmd):].strip()
                break
        else:
            print('Unknown internal command')
            return False
        method = getattr(self, RESERVED_COMMANDS[command_name])
        try:
            result = method(value) if value else method()
            if result is not None:
                print(result)
        except TypeError as exc:
            self.logger.exception(exc)
            return False
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
                self.run_internal_command(command)
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
