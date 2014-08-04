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

from cliff.command import Command

from fuelclient.cli.parser import parser as obsolete_parser


class HelpAction(argparse.Action):
    """Provide a custom action so the -h and --help options
    to the main app will print a list of the commands.

    The commands are determined by checking the CommandManager
    instance, passed in as the "default" value for the action.
    """
    def __call__(self, parser, namespace, values, option_string=None):
        app = self.default
        parser.print_help(app.stdout)
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

        app.stdout.write(obsolete_parser.help_string)
        sys.exit(0)


class HelpCommand(Command):
    pass
