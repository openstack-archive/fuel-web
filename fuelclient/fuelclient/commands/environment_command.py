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

from cliff import command
from cliff import lister
from cliff import show

from fuelclient.cli import error
from fuelclient.mixins import environment_mixins
from fuelclient import objects


class EnvCreate(environment_mixins.EnvShowMixin, show.ShowOne):
    """Creates environment with given attributes
    """
    def get_parser(self, prog_name):
        parser = super(EnvCreate, self).get_parser(prog_name)

        parser.add_argument(
            'name',
            type=str,
            help='Name for new environment'
        )

        parser.add_argument(
            'rel',
            type=int,
            help='Id of release for environment'
        )

        parser.add_argument(
            '-m',
            '--mode',
            type=str,
            choices=['ha', 'multinode'],
            dest='mode',
            default='ha',
            help='Mode of new environment'
        )

        parser.add_argument(
            '--net',
            '--net-provider',
            type=str,
            choices=['nova', 'neutron'],
            dest='net',
            default='nova',
            help='Network provider for new environment',
        )

        parser.add_argument(
            '--nst',
            '--network-segmentation-type',
            type=str,
            choices=['vlan', 'gre'],
            dest='nst',
            default=None,
            help='Network segmentation type to used with Neutron',
        )

        return parser

    def take_action(self, parsed_args):
        data_to_send = dict()
        # validate network arguments
        if getattr(parsed_args, 'net') == 'neutron':
            if not getattr(parsed_args, 'nst'):
                raise error.ArgumentException(
                    'You must supply`--network-segmentation-type` '
                    'argument for Neutron network provider'
                )
            data_to_send['net_provider'] = 'neutron'
        else:
            data_to_send['net_provider'] = 'nova_network'

        data_to_send['name'] = parsed_args.name
        data_to_send['release_id'] = parsed_args.rel
        data_to_send['mode'] = \
            'ha_compact' if parsed_args.mode == 'ha' else 'multinode'
        data_to_send['net_segment_type'] = parsed_args.nst

        env = objects.Environment.create(data_to_send)

        data_to_display = self.get_data_to_display(env.data)
        return(self.columns_names, data_to_display)


class EnvList(environment_mixins.EnvShowMixin, lister.Lister):
    """Show list of all avaliable envrionments
    """

    def take_action(self, parsed_args):

        data = objects.Environment.get_all_data()

        data = (self.get_data_to_display(elem) for elem in data)

        return (self.columns_names, data)


class EnvShow(environment_mixins.EnvShowMixin, show.ShowOne):
    """Show info about environment with given id
    """

    def get_parser(self, prog_name):
        parser = super(EnvShow, self).get_parser(prog_name)

        parser.add_argument(
            'env_id',
            type=int,
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
            'env_id',
            type=int,
            help='Id of environment to be deleted.'
        )
        return parser

    def take_action(self, parsed_args):
        env = objects.Environment(parsed_args.env_id)

        env.delete()

        self.app.stdout.write('Environment with id {0} was deleted\n'
                              .format(parsed_args.env_id))


class EnvUpdate(environment_mixins.EnvShowMixin,
                environment_mixins.EnvUpdateMixin, show.ShowOne):
    """Change given attributes for env
    """

    def get_parser(self, prog_name):
        parser = super(EnvUpdate, self).get_parser(prog_name)

        parser.add_argument(
            'env_id',
            type=int,
            help='Id of environment to be updated'
        )

        parser.add_argument(
            'name',
            type=str,
            help='New name for environment'
        )

        parser.add_argument(
            'mode',
            type=str,
            choices=['ha', 'multinode'],
            help='New mode for environment'
        )

        return parser

    def take_action(self, parsed_args):
        # convert 'ha' value to 'ha_compact'
        if getattr(parsed_args, 'mode') == 'ha':
            setattr(parsed_args, 'mode', 'ha_compact')

        env = objects.Environment(obj_id=parsed_args.env_id)
        data = self.update_env_attributes(parsed_args, env)
        data_to_display = self.get_data_to_display(data)

        return(
            self.columns_names,
            data_to_display
        )


class EnvUpgrade(environment_mixins.EnvUpdateMixin, command.Command):
    """Upgrades env to given relese
    """

    def get_parser(self, prog_name):
        parser = super(EnvUpgrade, self).get_parser(prog_name)

        parser.add_argument(
            'env_id',
            type=int,
            help='Id of environment to be upgraded'
        )

        parser.add_argument(
            'pending_release_id',
            type=int,
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
