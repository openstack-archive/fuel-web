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

from tasklib import config
from tasklib import logger


class CmdApi(object):

    def __init__(self):
        self.parser = argparse.ArgumentParser(
            description=textwrap.dedent(__doc__),
            formatter_class=argparse.RawDescriptionHelpFormatter)
        self.subparser = self.parser.add_subparsers(
            title='actions',
            description='Supported actions',
            help='Provide of one valid actions')
        self.register_actions()

    def register_actions(self):
        task_arg = [(('task',), {'type': str})]
        self.register_parser('list')
        self.register_parser('config')
        for name in ('run', 'daemon', 'runrep', 'report', 'status'):
            self.register_parser(name, task_arg)

    def register_parser(self, func_name, arguments=()):
        parser = self.subparser.add_parser(func_name)
        parser.set_defaults(func=getattr(self, func_name))
        for args, kwargs in arguments:
            parser.add_argument(*args, **kwargs)

    def parse(self, *args):
        parsed = self.parser.parse_args(args)
        parsed.func(parsed)

    def list(self, args):
        pass

    def run(self, args):
        pass

    def daemon(self, args):
        pass

    def runrep(self, args):
        pass

    def report(self, args):
        pass

    def status(self, args):
        pass

    def config(self, args):
        print(config.Config())


def main():
    logger.setup_logging()
    api = CmdApi()
    api.parse(*sys.argv[1:])
