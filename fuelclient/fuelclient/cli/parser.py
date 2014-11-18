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
from fuelclient import profiler


class Parser:
    """Parser class - encapsulates argparse's ArgumentParser
    and based on available actions, serializers and additional flags
    populates it.
    """
    def __init__(self, argv):
        self.args = argv
        self.parser = argparse.ArgumentParser(
            usage="""
            Configuration for client you can find in
            /etc/fuel/client/config.yaml. If you don't have this file please
            create it i.e.:
            "SERVER_ADDRESS": "127.0.0.1",
            "LISTEN_PORT": "8000",
            "KEYSTONE_USER": "admin",
            "KEYSTONE_PASS": "admin"

            fuel [optional args] <namespace> [action] [flags]"""
        )
        self.universal_flags = []
        self.credential_flags = []
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

        if profiler.profiling_enabled():
            handler_name = parsed_params.action
            method_name = ''.join([method for method in parsed_params.__dict__
                                   if getattr(parsed_params, method) is True])
            prof = profiler.Profiler(method_name, handler_name)

        actions[parsed_params.action].action_func(parsed_params)

        if profiler.profiling_enabled():
            prof.save_data()

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
        self.credential_flags.append('--user')
        self.credential_flags.append('--password')
        self.parser.add_argument(
            "--user",
            dest="user",
            type=str,
            help="credentials for keystone authentication user",
            default=None
        )
        self.parser.add_argument(
            "--password",
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

        # move general used flags before actions, otherwise they will be used
        # as a part of action by action_generator
        for flag in self.credential_flags:
            self.move_argument_before_action(flag)

        for flag in self.universal_flags:
            self.move_argument_before_action(flag, has_value=False)

        self.move_argument_after_action("--env", )

    def move_argument_before_action(self, flag, has_value=True):
        """We need to move general argument before action, we use them
        not directly in action but in APIClient.
        """
        for arg in self.args:
            if flag in arg:
                if "=" in arg or not has_value:
                    index_of_flag = self.args.index(arg)
                    flag = self.args.pop(index_of_flag)
                    self.args.insert(1, flag)
                else:
                    try:
                        index_of_flag = self.args.index(arg)
                        flag = self.args.pop(index_of_flag)
                        value = self.args.pop(index_of_flag)
                        self.args.insert(1, value)
                        self.args.insert(1, flag)
                    except IndexError:
                            raise ParserException(
                                'Corresponding value must follow "{0}" flag'
                                .format(arg)
                            )
                    break

    def move_argument_after_action(self, flag):
        for arg in self.args:
            if flag in arg:
                # if declaration with '=' sign (e.g. --env-id=1)
                if "=" in arg:
                    index_of_flag = self.args.index(arg)
                    flag = self.args.pop(index_of_flag)
                    self.args.append(flag)
                else:
                    try:
                        index_of_flag = self.args.index(arg)
                        self.args.pop(index_of_flag)
                        flag = self.args.pop(index_of_flag)
                        self.args.append(arg)
                        self.args.append(flag)
                    except IndexError:
                        raise ParserException(
                            'Corresponding value must follow "{0}" flag'
                            .format(arg)
                        )
                break


@exceptions_decorator
def main(args=sys.argv):
    parser = Parser(args)
    parser.parse()
