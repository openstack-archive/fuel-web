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

import sys
import argparse

from fuelclient.cli.arguments import get_version_arg
from fuelclient.cli.arguments import get_fuel_version_arg
from fuelclient.cli.error import exceptions_decorator
from fuelclient.cli.error import ParserException
from fuelclient.cli.arguments import substitutions
from fuelclient.cli.serializers import serializers
from fuelclient.cli.actions import actions


class Parser:
    def __init__(self):
        self.parser = argparse.ArgumentParser(
            usage="fuel [optional args] <namespace> [action] [flags]"
        )

        subparsers = self.parser.add_subparsers(
            title="Namespaces",
            metavar="",
            dest="action",
            help='actions'
        )
        self.generate_actions(subparsers)
        self.add_version_args()
        self.add_debug_arg()
        self.add_serializers_args()
        self.prepare_args()

    def generate_actions(self, subparsers):
        for action, action_object in actions.iteritems():
            action_parser = subparsers.add_parser(
                action,
                prog="fuel {0}".format(action),
                help=action_object.__doc__,
                formatter_class=argparse.RawTextHelpFormatter,
                epilog=action_object.examples
            )
            for argument in action_object.args:
                action_parser.add_argument(
                    *argument["args"],
                    **argument["params"]
                )

    def parse(self):
        parsed_params, other_params = self.parser.parse_known_args()
        if parsed_params.action not in actions:
            self.parser.print_help()
            sys.exit(0)
        exceptions_decorator(
            actions[parsed_params.action].action_func
        )(parsed_params)

    def add_serializers_args(self):
        for serializer in serializers:
            format_name = serializer.format
            self.parser.add_argument(
                "--{0}".format(format_name),
                dest=format_name,
                action="store_true",
                help="prints only {0} to stdout".format(format_name),
                default=False
            )

    def add_debug_arg(self):
        self.parser.add_argument(
            "--debug",
            dest="debug",
            action="store_true",
            help="prints details of all HTTP request",
            default=False
        )

    def add_version_args(self):
        for args in (get_version_arg(), get_fuel_version_arg()):
            self.parser.add_argument(*args["args"], **args["params"])

    def prepare_args(self):
        # replace some args from dict substitutions
        sys.argv = map(
            lambda x: substitutions.get(x, x),
            sys.argv
        )
        # move --json and --debug flags before any action
        for flag in ["--json", "--debug", "--yaml"]:
            if flag in sys.argv:
                sys.argv.remove(flag)
                sys.argv.insert(1, flag)

        for arg in sys.argv:
            if "--env" in arg:
                # if declaration with '=' sign (e.g. --env-id=1)
                if "=" in arg:
                    index_of_env = sys.argv.index(arg)
                    env = sys.argv.pop(index_of_env)
                    sys.argv.append(env)
                else:
                    try:
                        index_of_env = sys.argv.index(arg)
                        sys.argv.pop(index_of_env)
                        env = sys.argv.pop(index_of_env)
                        sys.argv.append(arg)
                        sys.argv.append(env)
                    except IndexError:
                        raise ParserException(
                            'Environment id must follow "{0}" flag'
                            .format(arg)
                        )
                break
