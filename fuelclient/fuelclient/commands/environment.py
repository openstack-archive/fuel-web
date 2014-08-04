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

import six

from cliff import command
from cliff import lister
from cliff import show

from fuelclient import objects


class EnvCreate(command.Command):
    """Creates environment with given attributes
    """
    def get_parser(self, prog_name):
        parser = super(EnvCreate, self).get_parser(prog_name)

        parser.add_argument(
            '-n',
            '--name',
            type=str,
            required=True,
            help='Name for new environment'
        )

        parser.add_argument(
            '--rel',
            '--release',
            type=int,
            help='Id of release for environment'
        )

        parser.add_argument(
            '-m',
            '--mode',
            type=str,
            required=False,
            default='ha',
            help='Mode of new environment'
        )

        parser.add_argument(
            '--net-provider',
            '--net',
            type=str,
            dest='net',
            choices=['nova', 'neutron'],
            required=False,
            default='nova',
            help='Network provider for new environment',
        )

        parser.add_argument(
            '--nst',
            '--network-segmentation-type',
            type=str,
            dest='nst',
            choices=['vlan', 'gre'],
            required=False,
            default=None,
            help='Network segmentation type to used with Neutron',
        )

        return parser

    def take_action(self, parsed_args):
        self.app.stdout.write(str(parsed_args))


class EnvShowMixin:
    """Supposed to provide common functionality
    and data for show and list commands
    """

    columns_names = ("id",
                     "status",
                     "name",
                     "mode",
                     "release_id",
                     "changes",
                     "pending_release_id")

    def get_data_to_display(self, data_elem):
        return [data_elem[field] for field in self.columns_names]


class EnvList(EnvShowMixin, lister.Lister):
    """Show list of all avaliable envrionments
    """

    def take_action(self, parsed_args):

        data = objects.Environment.get_all_data()

        data = (self.get_data_to_display(elem) for elem in data)

        return (self.columns_names, data)


class EnvShow(EnvShowMixin, show.ShowOne):
    """Show info about environment with given id
    """

    def get_parser(self, prog_name):
        parser = super(EnvShow, self).get_parser(prog_name)

        parser.add_argument(
            '--env-id',
            type=int,
            required=True,
            help='Id of environment to be displayed.'
        )
        return parser

    def take_action(self, parsed_args):
        env_data = objects.Environment(obj_id=parsed_args.env_id).data
        env_data = self.get_data_to_display(env_data)

        return (self.columns_names, env_data)


class EnvDelete(command.Command):
    """Delete environment with given id
    """

    def get_parser(self, prog_name):
        parser = super(EnvDelete, self).get_parser(prog_name)

        parser.add_argument(
            '--env-id',
            type=int,
            required=True,
            help='Id of environment to be deleted.'
        )
        return parser

    def take_action(self, parsed_args):
        env = objects.Environment(parsed_args.env_id)

        env.delete()

        self.app.stdout.write('Environment with id={0} was deleted\n'
                              .format(parsed_args.env_id))


class EnvUpdateMixin:
    """Incorporates method for updating particular env.
    This method is used in both EnvUpdate and EnvUpgrade
    commands.
    """

    # stores names for env attributes to be retrived from  parsed_args
    attributes_names = ('mode',
                        'name',
                        'pending_release_id')

    def update_env_attributes(self, parsed_args, env):
        """emit update operation on given env
        """
        args_data = parsed_args.__dict__

        update_kwargs = dict()
        for arg_name, arg_value in six.iteritems(args_data):
            if arg_name in self.attributes_names:
                update_kwargs[arg_name] = arg_value

        env.set(update_kwargs)

        return update_kwargs


class EnvUpdate(EnvUpdateMixin, show.ShowOne):
    """Change given attributes for env
    """

    def get_parser(self, prog_name):
        parser = super(EnvUpdate, self).get_parser(prog_name)

        parser.add_argument(
            '--env-id',
            type=int,
            required=True,
            help='Id of environment to be updated'
        )

        parser.add_argument(
            '--name',
            type=str,
            help='New name for environment'
        )

        parser.add_argument(
            '--mode',
            type=str,
            choices=['ha', 'multinode'],
            help='New mode for environment'
        )

        return parser

    def take_action(self, parsed_args):

        env = objects.Environment(obj_id=parsed_args.env_id)
        updated_attributes = self.update_env_attributes(parsed_args, env)

        # pring to stdout message
        self.app.stdout.write("Following attributes are changed for "
                              "the environment: \n")
        return(
            six.iterkeys(updated_attributes),
            six.itervalues(updated_attributes)
        )


class EnvUpgrade(EnvUpdateMixin, command.Command):
    """Upgrades env to given relese
    """

    def get_parser(self, prog_name):
        parser = super(EnvUpgrade, self).get_parser(prog_name)

        parser.add_argument(
            '--env-id',
            type=int,
            required=True,
            help='Id of environment to be upgraded'
        )

        parser.add_argument(
            ['--release', '--rel'],
            type=int,
            dest='pending_release_id',
            required=True,
            help='Relese id for updating env to'
        )

        return parser

    def take_action(self, parsed_args):
        env = objects.Environment(obj_id=parsed_args.env_id)

        self.update_env_attributes(parsed_args, env)
        update_task_id = env.update_env().id

        self.app.stdout.write(
            "Update process for environment has been started. "
            "Update task id is {0}\n".format(update_task_id)
        )
