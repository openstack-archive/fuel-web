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

import logging
import os
import yaml

from tasklib.actions import action
from tasklib import exceptions
from tasklib import utils

log = logging.getLogger(__name__)


class PuppetAction(action.Action):
    LAST_RUN_REPORT = '/var/lib/puppet/state/last_run_report.yaml'

    def run(self):
        log.debug('Running puppet task %s with command %s',
                  self.task.name, self.command)

        self.report = {}
        self.resources = {}

        # run the puppet apply
        exit_code, stdout, stderr = utils.execute(self.command)

        log.debug(
            'Task %s with command %s\n returned code %s\n out %s err%s',
            self.task.name, self.command, exit_code, stdout, stderr)

        # 0 - no changes
        # 2 - was some changes but successfull
        # 4 - failures during transaction
        # 6 - changes and failures

        self.report = self.load_report_file()
        deployment_status = self.report.get('status', None)
        events = self.report.get('metrics', {}).get('events', {}).get('values', {})
        metrics = {}
        for event in events:
            metrics[event[1]] = event[2]

        # this will be used to create report xUnit files for Puppet action
        # or to view report and profiling data intercatively
        self.resources = self.resource_statuses(self.report)

        # Success criteria by the exit code.
        exit_code_success = exit_code in [0, 2]

        # Success criteria by deployment status in the report.
        # If there is no deployment status data then report failure.
        if deployment_status:
            deployment_status_success = deployment_status != 'failed'
        else:
            deployment_status_success = False

        # Zero total resources count means something is wrong.
        # You are not going to apply an empty manifest, aren't you?
        # Catalog compile failure? Accidently empty manifest?
        total_resources_success = len(self.resources) != 0

        # There should be no failed resources.
        # If there are no metrics then report failure.
        if 'Failure' in metrics:
            failed_resources_success = metrics['Failure'] == 0
        else:
            failed_resources_success = False

        log.debug("Puppet: EC: %s, DS: %s, TR: %s, FR: %s" %
                  (exit_code_success,
                   deployment_status_success,
                   total_resources_success,
                   failed_resources_success))

        if not (exit_code_success and
                deployment_status_success and
                total_resources_success and
                failed_resources_success):
            raise exceptions.Failed()

        return exit_code

    def resource_statuses(self, report):
        resource_statuses = report.get('resource_statuses', {})
        filtered_statuses = {}
        for title, params in resource_statuses.iteritems():
            if self.filter_useless_resources(title):
                filtered_statuses[title] = params
        return filtered_statuses

    def filter_useless_resources(self, resource_title):
        if resource_title.startswith('Schedule'):
            return False
        if resource_title.startswith('Filebucket'):
            return False
        return True

    def construct_ruby_object(self, loader, suffix, node):
        return loader.construct_yaml_map(node)

    def construct_ruby_sym(self, loader, node):
        return loader.construct_yaml_str(node)

    def extend_yaml(self):
        yaml.add_multi_constructor(u"!ruby/object:", self.construct_ruby_object)
        yaml.add_constructor(u"!ruby/sym", self.construct_ruby_sym)

    def load_report_file(self):
        try:
            f = open(self.LAST_RUN_REPORT, 'r')
            raw_report = f.read()
            f.close()
        except IOError:
            return None

        if raw_report:
            self.extend_yaml()
            return yaml.load(raw_report)

    @property
    def manifest(self):
        return (self.task.metadata.get('puppet_manifest') or
                self.config['puppet_manifest'])

    @property
    def puppet_options(self):
        if 'puppet_options' in self.task.metadata:
            return self.task.metadata['puppet_options']
        return self.config['puppet_options']

    @property
    def puppet_modules(self):
        return (self.task.metadata.get('puppet_modules') or
                self.config['puppet_modules'])

    @property
    def command(self):
        cmd = ['puppet', 'apply', '--detailed-exitcodes']
        if self.puppet_modules:
            cmd.append('--modulepath={0}'.format(self.puppet_modules))
        if self.puppet_options:
            cmd.append(self.puppet_options)
        if self.config['debug']:
            cmd.append('--debug --verbose --evaltrace --trace')
        cmd.append(os.path.join(self.task.dir, self.manifest))
        return ' '.join(cmd)
