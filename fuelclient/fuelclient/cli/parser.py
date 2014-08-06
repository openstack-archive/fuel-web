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

import argparse
import sys

from fuelclient.cli.actions import actions
from fuelclient.cli.arguments import get_fuel_version_arg
from fuelclient.cli.arguments import get_version_arg
from fuelclient.cli.arguments import substitutions
from fuelclient.cli.error import exceptions_decorator
from fuelclient.cli.error import ParserException
from fuelclient.cli.serializers import Serializer


class Parser:
    """Parser class - encapsulates argparse's ArgumentParser
    and based on available actions, serializers and additional flags
    populates it.
    """
    def __init__(self):
        self.args = sys.argv
        self.parser = argparse.ArgumentParser(
            usage="fuel [optional args] <namespace> [action] [flags]"
        )
        self.universal_flags = []
        self.subparsers = self.parser.add_subparsers(
            title="Namespaces",
            metavar="",
            dest="action",
            help='actions'
        )
        self.generate_actions()
        self.add_version_args()
        self.add_debug_arg()
        self.add_keystone_credentials_args()
        self.add_serializers_args()

    def generate_actions(self):
        for action, action_object in actions.iteritems():
            action_parser = self.subparsers.add_parser(
                action,
                prog="fuel {0}".format(action),
                help=action_object.__doc__,
                formatter_class=argparse.RawTextHelpFormatter,
                epilog=action_object.examples
            )
            for argument in action_object.args:
                if isinstance(argument, dict):
                    action_parser.add_argument(
                        *argument["args"],
                        **argument["params"]
                    )
                elif isinstance(argument, tuple):
                    required = argument[0]
                    group = action_parser.add_mutually_exclusive_group(
                        required=required)
                    for argument_in_group in argument[1:]:
                        group.add_argument(
                            *argument_in_group["args"],
                            **argument_in_group["params"]
                        )

    def parse(self):
        self.prepare_args()
        if len(self.args) < 2:
            self.parser.print_help()
            sys.exit(0)
        parsed_params, _ = self.parser.parse_known_args(self.args[1:])
        if parsed_params.action not in actions:
            self.parser.print_help()
            sys.exit(0)
        actions[parsed_params.action].action_func(parsed_params)

    def add_serializers_args(self):
        for format_name in Serializer.serializers.keys():
            serialization_flag = "--{0}".format(format_name)
            self.universal_flags.append(serialization_flag)
            self.parser.add_argument(
                serialization_flag,
                dest=format_name,
                action="store_true",
                help="prints only {0} to stdout".format(format_name),
                default=False
            )

    def add_debug_arg(self):
        self.universal_flags.append("--debug")
        self.parser.add_argument(
            "--debug",
            dest="debug",
            action="store_true",
            help="prints details of all HTTP request",
            default=False
        )

    def add_keystone_credentials_args(self):
        self.parser.add_argument(
            "--os-username",
            dest="user",
            type=str,
            help="credentials for keystone authentication user",
            default=None
        )
        self.parser.add_argument(
            "--os-password",
            dest="password",
            type=str,
            help="credentials for keystone authentication password",
            default=None
        )

    def add_version_args(self):
        for args in (get_version_arg(), get_fuel_version_arg()):
            self.parser.add_argument(*args["args"], **args["params"])

    def prepare_args(self):
        # replace some args from dict substitutions
        self.args = map(
            lambda x: substitutions.get(x, x),
            self.args
        )
        # move --json and --debug flags before any action
        for flag in self.universal_flags:
            if flag in self.args:
                self.args.remove(flag)
                self.args.insert(1, flag)

        self.move_argument_before_action("--env", )

    def move_argument_before_action(self, argument):
        for arg in self.args:
            if argument in arg:
                # if declaration with '=' sign (e.g. --env-id=1)
                if "=" in arg:
                    index_of_env = self.args.index(arg)
                    env = self.args.pop(index_of_env)
                    self.args.append(env)
                else:
                    try:
                        index_of_env = self.args.index(arg)
                        self.args.pop(index_of_env)
                        env = self.args.pop(index_of_env)
                        self.args.append(arg)
                        self.args.append(env)
                    except IndexError:
                        raise ParserException(
                            'Corresponding value must follow "{0}" flag'
                            .format(arg)
                        )
                break


@exceptions_decorator
def main():
    parser = Parser()
    parser.parse()
