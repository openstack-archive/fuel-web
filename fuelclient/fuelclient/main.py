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
import sys

from cliff import app
from cliff.commandmanager import CommandManager

# need only for backwards compability with previous version api
# TODO(aroma): remove after all subcommands will be implemented using cliff
from fuelclient.cli import parser as obsolete_parser

from fuelclient.cli import arguments
from fuelclient.utils import custom_actions
from fuelclient.utils import custom_commands


LOG = logging.getLogger(__name__)


class FuelClient(app.App):
    """Main cliff application class.
    Performs load of commands which is described as entrypoints in
    setu.py file and initial setup (i.e. logging, global opts, commands
    execution control, hooks, configuring standart streams) for whole app.
    """

    def __init__(self, *args, **kwargs):
        """Initialize the application.
        """
        super(FuelClient, self).__init__(*args, **kwargs)
        # ovveride default help command in order to support prev code base
        # TODO(aroma): remove it after full cliff implementation
        self.command_manager.add_command('help', custom_commands.HelpCommand)

    def build_option_parser(self, description, version,
                            argparse_kwargs=None):
        """At this time the method redefinition is needed only for purpose
        of supplying backwards compability with previous version of api.
        Such supply lies in customization of HelpAction for help
        option which is supposed to provide help for prev version in addition
        to help for cliff implemented subcomands. Consider to remove it when
        whole set of operation will be implemented using cliff utils.
        """
        argparse_kwargs = argparse_kwargs or {}
        # override `help` argument
        argparse_kwargs.update({'conflict_handler': 'resolve'})
        parser = super(FuelClient, self).build_option_parser(
            description=description,
            version=version,
            argparse_kwargs=argparse_kwargs
        )

        parser.add_argument(
            '-h', '--help',
            action=custom_actions.HelpAction,
            nargs=0,
            default=self,  # tricky
            help="show this help message and exit",
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

    def configure_logging(self):
        super(FuelClient, self).configure_logging()

        # there is issue with management url processing by keystone client
        # code in our workflow, so we have to mute appropriate keystone
        # loggers in order to get rid from unprocessable errors
        logging.getLogger('keystoneclient.httpclient')\
            .setLevel(logging.ERROR)

        # increase level of loggin for urllib3 to avoid of displaying
        # of useless messages. List of logger names is needed for
        # consistency on different execution environments that could have
        # installed requests packages (which is used urllib3) of different
        # versions in turn
        for logger_name in ('requests.packages.urllib3.connectionpool',
                            'urllib3.connectionpool'):
            logging.getLogger(logger_name).setLevel(logging.WARNING)


def main(argv=sys.argv[1:]):
    fuelclient_app = FuelClient(
        description='Command line interface for Nailgun',
        version='1.0',
        command_manager=CommandManager('fuelclient')
    )
    return fuelclient_app.run(argv)
