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
import logging
import sys

from cliff import app
from cliff.commandmanager import CommandManager
from cliff.complete import CompleteCommand
from cliff.interactive import InteractiveApp

# need only for backwards compability with previous version api
# TODO(aroma): remove after all subcommands will be implemented using cliff
from fuelclient.cli import parser as obsolete_parser

from fuelclient.cli import arguments
from fuelclient.utils import custom_actions
from fuelclient.utils import custom_commands


LOG = logging.getLogger(__name__)


class FuelClient(app.App):

    def __init__(self, description='Command line interface for Nailgun',
                 version='0.2',
                 command_manager=CommandManager('fuelclient'),
                 stdin=None, stdout=None, stderr=None,
                 interactive_app_factory=InteractiveApp):
        """Initialize the application.
        """
        self.command_manager = command_manager
        self.command_manager.add_command('help', custom_commands.HelpCommand)
        self.command_manager.add_command('complete', CompleteCommand)
        self._set_streams(stdin, stdout, stderr)
        self.interactive_app_factory = interactive_app_factory
        self.parser = self.build_option_parser(description, version)
        self.interactive_mode = False
        self.interpreter = None

    def build_option_parser(self, description, version,
                            argparse_kwargs=None):
        """Return an argparse option parser for this application.

        Subclasses may override this method to extend
        the parser with more global options.

        :param description: full description of the application
        :paramtype description: str
        :param version: version number for the application
        :paramtype version: str
        :param argparse_kwargs: extra keyword argument passed to the
                                ArgumentParser constructor
        :paramtype extra_kwargs: dict

        At this time the method redefinition is needed only for purpose
        of supplying backwards compability with previous version of api.
        Such supply lies in customization of HelpAction for help
        option which is supposed to provide help for prev version in addition
        to help for cliff implemented subcomands. Consider to remove it when
        whole set of operation will be implemented using cliff utils.
        """
        argparse_kwargs = argparse_kwargs or {}
        parser = argparse.ArgumentParser(
            description=description,
            add_help=False,
            **argparse_kwargs
        )
        parser.add_argument(
            '--version',
            action='version',
            version='%(prog)s {0}'.format(version),
        )
        parser.add_argument(
            '-v', '--verbose',
            action='count',
            dest='verbose_level',
            default=self.DEFAULT_VERBOSE_LEVEL,
            help='Increase verbosity of output. Can be repeated.',
        )
        parser.add_argument(
            '--log-file',
            action='store',
            default=None,
            help='Specify a file to log output. Disabled by default.',
        )
        parser.add_argument(
            '-q', '--quiet',
            action='store_const',
            dest='verbose_level',
            const=0,
            help='suppress output except warnings and errors',
        )
        parser.add_argument(
            '-h', '--help',
            action=custom_actions.HelpAction,
            nargs=0,
            default=self,  # tricky
            help="show this help message and exit",
        )
        parser.add_argument(
            '--debug',
            default=False,
            action='store_true',
            help='show tracebacks on errors',
        )
        parser.add_argument(
            '--fuel-version',
            action=arguments.FuelVersionAction,
            help="show Fuel server's version number and exit"
        )
        return parser

    def run_subcommand(self, argv):
        """Redefinition of corresponding parent class method which is done
        to supply backward compability with previous fuelclient api version.
        Consider to remove this code when all subcommads implementation
        will be migrated to cliff codebase.
        """
        try:
            subcommand = self.command_manager.find_command(argv)
        except ValueError as err:
            LOG.info("Command haven't implemented yet. Fallback to "
                     "previous version of fuelclient api")
            obsolete_parser.main()
            return 2

        cmd_factory, cmd_name, sub_argv = subcommand
        cmd = cmd_factory(self, self.options)
        err = None
        result = 1
        try:
            self.prepare_to_run_command(cmd)
            full_name = (cmd_name
                         if self.interactive_mode
                         else ' '.join([self.NAME, cmd_name])
                         )
            cmd_parser = cmd.get_parser(full_name)
            parsed_args = cmd_parser.parse_args(sub_argv)
            result = cmd.run(parsed_args)
        except Exception as err:
            if self.options.debug:
                LOG.exception(err)
            else:
                LOG.error(err)
            try:
                self.clean_up(cmd, result, err)
            except Exception as err2:
                if self.options.debug:
                    LOG.exception(err2)
                else:
                    LOG.error('Could not clean up: %s', err2)
            if self.options.debug:
                raise
        else:
            try:
                self.clean_up(cmd, result, None)
            except Exception as err3:
                if self.options.debug:
                    LOG.exception(err3)
                else:
                    LOG.error('Could not clean up: %s', err3)
        return result


def main(argv=sys.argv[1:]):
    fuelclient_app = FuelClient()
    return fuelclient_app.run(argv)
