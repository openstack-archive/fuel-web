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

from cliff import command
from cliff import lister
from cliff import show

from fuelclient.cli import error
from fuelclient import mixins
from fuelclient.mixins import environment_mixins
from fuelclient import objects


class EnvList(mixins.CommandBaseMixin,
              mixins.ShowMixin,
              environment_mixins.EnvShowMixin,
              lister.Lister):
    """Show list of all avaliable envrionments
    """
    nailgun_entity = objects.Environment


class EnvShow(mixins.CommandBaseMixin,
              mixins.ShowMixin,
              environment_mixins.EnvShowMixin,
              show.ShowOne):
    """Show info about environment with given id
    """

    nailgun_entity = objects.Environment

    def get_parser(self, prog_name):
        parser = super(EnvShow, self).get_parser(prog_name)

        parser.add_argument(
            'id',
            type=int,
            help='Id of the nailgun entity to be processed.'
        )
        return parser


class EnvCreate(mixins.CommandBaseMixin,
                mixins.ShowMixin,
                mixins.environment_mixins.EnvShowMixin,
                show.ShowOne):
    """Creates environment with given attributes
    """
    nailgun_entity = objects.Environment

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

    def operation(self, parsed_args):
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

        # avoid possible issues with encoding
        parsed_args.name = \
            parsed_args.name.decode(sys.getfilesystemencoding())

        data_to_send['name'] = parsed_args.name
        data_to_send['release_id'] = parsed_args.rel
        data_to_send['mode'] = \
            'ha_compact' if parsed_args.mode == 'ha' else 'multinode'
        data_to_send['net_segment_type'] = parsed_args.nst

        data_to_return = self.nailgun_entity.create(data_to_send).data

        return data_to_return


class EnvDelete(mixins.CommandBaseMixin,
                command.Command):
    """Delete environment with given id
    """

    nailgun_entity = objects.Environment

    def get_parser(self, prog_name):
        parser = super(EnvDelete, self).get_parser(prog_name)

        parser.add_argument(
            'id',
            type=int,
            help='Id of the nailgun entity to be processed.'
        )
        return parser

    def operation(self, parsed_args):
        entity_instance = self.nailgun_entity(obj_id=parsed_args.id)
        entity_instance.delete()

        self.msg_to_display = ('Environment with id {0} was deleted\n'
                               .format(parsed_args.id))
        return None


class EnvUpdate(mixins.CommandBaseMixin,
                mixins.ShowMixin,
                environment_mixins.EnvShowMixin,
                environment_mixins.EnvUpdateMixin,
                show.ShowOne):
    """Change given attributes for env
    """

    nailgun_entity = objects.Environment

    def get_parser(self, prog_name):
        parser = super(EnvUpdate, self).get_parser(prog_name)

        parser.add_argument(
            'id',
            type=int,
            help='Id of the nailgun entity to be processed.'
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

    def operation(self, parsed_args):
        # convert 'ha' value to 'ha_compact'
        if getattr(parsed_args, 'mode') == 'ha':
            setattr(parsed_args, 'mode', 'ha_compact')

        entity_instance = self.nailgun_entity(obj_id=parsed_args.id)
        data_to_return = self.update_env_attributes(parsed_args,
                                                    entity_instance)
        return data_to_return


class EnvUpgrade(mixins.CommandBaseMixin,
                 environment_mixins.EnvUpdateMixin,
                 command.Command):
    """Upgrades env to given relese
    """

    nailgun_entity = objects.Environment

    def get_parser(self, prog_name):
        parser = super(EnvUpgrade, self).get_parser(prog_name)

        parser.add_argument(
            'id',
            type=int,
            help='Id of the nailgun entity to be processed.'
        )

        parser.add_argument(
            'pending_release_id',
            type=int,
            help='Relese id for updating env to'
        )

        return parser

    def operation(self, parsed_args):
        entity_instance = self.nailgun_entity(obj_id=parsed_args.id)

        self.update_env_attributes(parsed_args, entity_instance)
        update_task_id = entity_instance.update_env().id

        self.msg_to_display = (
            "Update process for environment has been started. "
            "Update task id is {0}\n".format(update_task_id)
        )

        return None
