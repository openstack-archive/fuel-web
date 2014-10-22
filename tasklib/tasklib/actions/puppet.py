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
    """Puppet action plugin.

    Implements support for Puppet type actions.
    Can apply a single manifest and determine success or failure.
    """
    LAST_RUN_REPORT = '/var/lib/puppet/state/last_run_report.yaml'
    report = None
    resources = None
    metrics = None
    exit_code = None
    stdout = None
    stderr = None

    def reset_mnemoization(self):
        """Reset saved variables

        :return:
        """
        self.report = None
        self.resources = None
        self.metrics = None
        self.exit_code = None
        self.stdout = None
        self.stderr = None

    def run_puppet(self):
        """Execute the puppet command

        :rtype: int
        """
        self.exit_code, self.stdout, self.stderr \
            = utils.execute(self.command)
        return self.exit_code

    @property
    def puppet_report(self):
        """Read and parse the report file

        :rtype : dict
        :return: Parsed Puppet report structure
        """
        if self.report:
            return self.report
        self.reset_mnemoization()
        self.report = self.load_report_file()
        return self.report

    @property
    def puppet_resources(self):
        """Parsed resource section of the report

        This will be used to create report xUnit files for Puppet action
        to view report and profiling data interactively
        :rtype: dict
        :return: Dictionary of resource structures
        """
        if self.resources:
            return self.resources
        if not self.puppet_report:
            return None
        resource_statuses = self.puppet_report.get('resource_statuses', {})
        self.resources = {}
        for title, params in resource_statuses.iteritems():
            if self.filter_useless_resources(title):
                self.resources[title] = params
        return self.resources

    @property
    def puppet_metrics(self):
        """Get metrics data from the events sections

        :rtype: dict
        :return: Dictionary of metric structures
        """
        if self.metrics:
            return self.metrics
        if not self.puppet_report:
            return None
        events = self.puppet_report\
            .get('metrics', {})\
            .get('events', {})\
            .get('values', {})
        self.metrics = {}
        for event in events:
            self.metrics[event[1]] = event[2]
        return self.metrics

    @property
    def success_deployment_status(self):
        """Get deployment status from report

        It should not be 'failed'
        :rtype: bool
        :return: deployment success from report
        """
        if not self.puppet_report:
            return False
        status = self.puppet_report.get('status', 'failed')
        return status != 'failed'

    @property
    def success_exit_code(self):
        """Success by exit code

        0 - no changes
        2 - was some changes but successful
        4 - failures during transaction
        6 - changes and failures
        :rtype: bool
        :return: success by Puppet exit code
        """
        return self.exit_code in [0, 2]

    @property
    def success_resource_count(self):
        """Success by non-zero resource count

        Zero total resources count means something is wrong.
        You are not going to apply an empty manifest, aren't you?
        Catalog compile failure? Accidentally empty manifest?
        :rtype: bool
        :return: success by positive resource count
        """
        resources = self.puppet_resources
        if not resources:
            return False
        return len(resources) != 0

    @property
    def success_fail_metrics(self):
        """Success by zero failed resources

        There should be no failed resources.
        If there are no metrics then report failure.
        :rtype: bool
        :return: success by zero fails in metrics
        """
        metrics = self.puppet_metrics
        if not metrics:
            return False
        return metrics.get('Failure', None) == 0

    @property
    def all_success_criterias(self):
        """Gather all success metrics

        :rtype: dict
        :return: Dictionary of success and failure criterias
        """
        criterias = {
            'exit_code': self.success_exit_code,
            'resource_count': self.success_resource_count,
            'fail_metrics': self.success_fail_metrics,
            'deployment_status': self.success_deployment_status,
        }
        return criterias

    def run(self):
        log.debug(
            "Running puppet task '%s' with command '%s'",
            self.task.name,
            self.command
        )

        self.run_puppet()

        log.debug(
            "Task '%s' with cmd '%s' returned code '%s' out: '%s' err: '%s'",
            self.task.name,
            self.command,
            self.exit_code,
            self.stdout,
            self.stderr
        )

        success = self.all_success_criterias
        log.debug("Success: %s", repr(success))

        if False in success.values():
            raise exceptions.Failed()

        return self.exit_code

    @classmethod
    def filter_useless_resources(cls, resource_title):
        """Resource filter function

        Used to remove useless resources from the report
        :param resource_title: str
        :rtype: bool
        :return: false if resource is useless
        """
        if resource_title.startswith('Schedule'):
            return False
        if resource_title.startswith('Filebucket'):
            return False
        return True

    @classmethod
    def construct_ruby_object(cls, loader, suffix, node):
        """Parse ruby objects

        :param loader:
        :param suffix:
        :param node:
        :return:
        """
        return loader.construct_yaml_map(node)

    @classmethod
    def construct_ruby_sym(cls, loader, node):
        """Parse ruby symbols

        :param loader:
        :param node:
        :return:
        """
        return loader.construct_yaml_str(node)

    @classmethod
    def extend_yaml(cls):
        """Extend yaml module to support Puppet reports

        :return:
        """
        yaml.add_multi_constructor(u"!ruby/object:",
                                   cls.construct_ruby_object)
        yaml.add_constructor(u"!ruby/sym",
                             cls.construct_ruby_sym)

    def load_report_file(self):
        """Read and parse the Puppet report file

        :rtype: dict
        :return: The parsed Puppet report
        """
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
        """Puppet manifests from tasks configuration

        :rtype: str
        :return: Manifest file name
        """
        return (self.task.metadata.get('puppet_manifest') or
                self.config['puppet_manifest'])

    @property
    def puppet_options(self):
        """Puppet options from configuration

        :rtype: str
        :return: String of Puppet options
        """
        if 'puppet_options' in self.task.metadata:
            return self.task.metadata['puppet_options']
        return self.config['puppet_options']

    @property
    def puppet_modules(self):
        """Path to Puppet modules from the configuration

        :rtype: str
        :return: The path to Puppet modules
        """
        return (self.task.metadata.get('puppet_modules') or
                self.config['puppet_modules'])

    @property
    def command(self):
        """Assemble the final command for execution

        :rtype: str
        :return: the command
        """
        cmd = ['puppet', 'apply', '--detailed-exitcodes']
        if self.puppet_modules:
            cmd.append('--modulepath={0}'.format(self.puppet_modules))
        if self.puppet_options:
            cmd.append(self.puppet_options)
        if self.config['debug']:
            cmd.append('--debug --verbose --evaltrace --trace')
        cmd.append(os.path.join(self.task.dir, self.manifest))
        return ' '.join(cmd)
