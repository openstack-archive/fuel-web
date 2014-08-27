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
import traceback

from fuelclient.cli.parser import parser as obsolete_parser


class HelpAction(argparse.Action):
    """Provide a custom action so the -h and --help options
    to the main app will print a list of the commands.

    The commands are determined by checking the CommandManager
    instance, passed in as the "default" value for the action.

    The reason for the class redefinition - customize help message
    processing so that it contains help not only for cliff defined
    commands but also for old code ones.
    """
    def __call__(self, parser, namespace, values, option_string=None):
        app = self.default

        # we need to display optional args section of help message
        # which will be containing such sections from two different parsers
        # for it we must somehow pass needed data to parser which format
        # method will be using
        opt_args_action_group = [
            action_group for action_group in parser._action_groups
            if action_group.title == 'optional arguments'
        ].pop()
        obsolete_parser.parser.new_action_group = opt_args_action_group

        old_cmds_help = obsolete_parser.parser.format_help()
        old_opt_args_help = obsolete_parser.parser.opt_args_help

        # print help for optional args: both new and old version of client
        #app.stdout.write(parser.format_help())
        app.stdout.write(old_opt_args_help)

        #parser.print_help(app.stdout)
        app.stdout.write('\nCommands:\n')
        command_manager = app.command_manager

        for name, ep in sorted(command_manager):
            try:
                factory = ep.load()
            except Exception as err:
                app.stdout.write('Could not load %r\n' % ep)
                if namespace.debug:
                    traceback.print_exc(file=app.stdout)
                continue
            try:
                cmd = factory(app, None)
            except Exception as err:
                app.stdout.write('Could not instantiate %r: %s\n' % (ep, err))
                if namespace.debug:
                    traceback.print_exc(file=app.stdout)
                continue
            one_liner = cmd.get_description().split('\n')[0]
            app.stdout.write('  %-13s  %s\n' % (name, one_liner))

        # write help for old version of code
        app.stdout.write('\n' + old_cmds_help)

        sys.exit(0)
