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

from cliff import lister

from fuelclient import utils


class BaseShowCommand(lister.Lister):

    columns_names = ()

    def take_action(self, parsed_args):
        if getattr(parsed_args, 'id', None):
            data = self.nailgun_entity(obj_id=parsed_args.id).data
            data = [data]  # for displaying consistency
        else:
            data = self.nailgun_entity.get_all_data()

        data = utils.get_display_data(self.columns_names, data)

        return (self.columns_names, data)
