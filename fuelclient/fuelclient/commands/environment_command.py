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

from fuelclient.cli import error
from fuelclient import commands as fuel_base_cmds
from fuelclient import objects
from fuelclient import utils


class EnvList(fuel_base_cmds.BaseShowCommand):
    """Show list of all avaliable envrionments
    """

    columns_names = ("id",
                     "status",
                     "name",
                     "mode",
                     "release_id",
                     "changes",
                     "net_provider")

    nailgun_entity = objects.Environment


class EnvShow(fuel_base_cmds.BaseShowCommand):
    """Show info about environment with given id
    """
    columns_names = ("id",
                     "status",
                     "name",
                     "mode",
                     "release_id",
                     "changes",
                     "net_provider")

    nailgun_entity = objects.Environment

    def get_parser(self, prog_name):
        parser = super(EnvShow, self).get_parser(prog_name)

        parser.add_argument(
            'id',
            type=int,
            help='Id of the nailgun entity to be processed.'
        )
        return parser


class EnvCreate(lister.Lister):
    """Creates environment with given attributes
    """

    columns_names = ("id",
                     "status",
                     "name",
                     "mode",
                     "release_id",
                     "changes",
                     "net_provider")

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

        # avoid possible issues with encoding
        parsed_args.name = \
            parsed_args.name.decode(sys.getfilesystemencoding())

        data_to_send['name'] = parsed_args.name
        data_to_send['release_id'] = parsed_args.rel
        data_to_send['mode'] = \
            'ha_compact' if parsed_args.mode == 'ha' else 'multinode'
        data_to_send['net_segment_type'] = parsed_args.nst

        data = self.nailgun_entity.create(data_to_send).data
        data = [data]
        data = utils.get_display_data(self.columns_names, data)

        return (self.columns_names, data)


class EnvDelete(command.Command):
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

    def take_action(self, parsed_args):
        entity_instance = self.nailgun_entity(obj_id=parsed_args.id)
        entity_instance.delete()

        self.app.stdout.write('Environment with id {0} was deleted\n'
                              .format(parsed_args.id))


class EnvUpdate(lister.Lister):
    """Change given attributes for env
    """

    columns_names = ("id",
                     "status",
                     "name",
                     "mode",
                     "release_id",
                     "changes",
                     "net_provider")

    attributes_to_update = ('mode',
                            'name',
                            'pending_release_id')

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

    def take_action(self, parsed_args):
        # convert 'ha' value to 'ha_compact'
        if getattr(parsed_args, 'mode') == 'ha':
            setattr(parsed_args, 'mode', 'ha_compact')

        entity_instance = self.nailgun_entity(obj_id=parsed_args.id)
        attributes_to_filter = parsed_args.__dict__
        data = utils.update_entity_attributes(entity_instance,
                                              self.attributes_to_update,
                                              attributes_to_filter)
        data = [data]
        data = utils.get_display_data(self.columns_names, data)
        return (self.columns_names, data)


class EnvUpgrade(command.Command):
    """Upgrades env to given relese
    """

    attributes_to_update = ('mode',
                            'name',
                            'pending_release_id')

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

    def take_action(self, parsed_args):
        entity_instance = self.nailgun_entity(obj_id=parsed_args.id)

        attributes_to_filter = parsed_args.__dict__
        utils.update_entity_attributes(entity_instance,
                                       self.attributes_to_update,
                                       attributes_to_filter)

        update_task_id = entity_instance.update_env().id

        msg = (
            "Update process for environment has been started. "
            "Update task id is {0}\n".format(update_task_id)
        )

        self.app.stdout.write(msg)
