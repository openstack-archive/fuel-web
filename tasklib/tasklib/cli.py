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
"""Tasklib cmd interface
"""

import argparse
import sys
import textwrap

import yaml

from tasklib import agent
from tasklib import config
from tasklib import task
from tasklib import logger
from tasklib import utils


class CmdApi(object):

    def __init__(self):
        self.parser = argparse.ArgumentParser(
            description=textwrap.dedent(__doc__),
            formatter_class=argparse.RawDescriptionHelpFormatter)
        self.subparser = self.parser.add_subparsers(
            title='actions',
            description='Supported actions',
            help='Provide of one valid actions')
        self.config = None
        self.register_options()
        self.register_actions()

    def register_options(self):
        self.parser.add_argument(
            '--config', '-c', dest='config', default=None,
            help='Path to configuration file')

    def register_actions(self):
        task_arg = [(('task',), {'type': str})]
        self.register_parser('list')
        self.register_parser('conf')
        for name in ('run', 'daemon', 'runrep', 'report', 'status', 'show'):
            self.register_parser(name, task_arg)

    def register_parser(self, func_name, arguments=()):
        parser = self.subparser.add_parser(func_name)
        parser.set_defaults(func=getattr(self, func_name))
        for args, kwargs in arguments:
            parser.add_argument(*args, **kwargs)

    def parse(self, args):
        parsed = self.parser.parse_args(args)
        self.config = config.Config(config_file=parsed.config)
        return parsed.func(parsed)

    def list(self, args):
        for task_dir in utils.find_all_tasks(self.config):
            print(task.Task.task_from_dir(task_dir, self.config))

    def show(self, args):
        meta = task.Task(args.task, self.config).metadata
        print(yaml.dump(meta, default_flow_style=False))

    def run(self, args):
        task_agent = agent.TaskAgent(args.task, self.config)
        return task_agent.run()

    def daemon(self, args):
        task_agent = agent.TaskAgent(args.task, self.config)
        task_agent.daemon()

    def runrep(self, args):
        """Run task and return report in arbitrary format"""

    def report(self, args):
        task_agent = agent.TaskAgent(args.task, self.config)
        print(task_agent.report())

    def status(self, args):
        task_agent = agent.TaskAgent(args.task, self.config)
        status = task_agent.status()
        exit_code = utils.exit_codes.get(status, 42)
        print(status)
        return exit_code

    def conf(self, args):
        print(self.config)


def main():
    logger.setup_logging()
    api = CmdApi()
    exit_code = api.parse(sys.argv[1:])
    exit(exit_code)
