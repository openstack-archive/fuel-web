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

import itertools


class CommandBaseMixin(object):

    def __init__(self, *args, **kwargs):
        if not getattr(self, 'columns_names', None):
            self.columns_names = []

        self.msg_to_display = ''

        super(CommandBaseMixin, self).__init__(*args, **kwargs)

    def _get_data_to_display(self, data_elem):
        return [data_elem[field] for field in self.columns_names]

    def _get_data_from_nailgun_entity(self, obj_id=None):
        if obj_id:
            return self.nailgun_entity(obj_id=obj_id).data

        return self.nailgun_entity.get_all_data()

    def take_action(self, parsed_args):
        data = self.operation(parsed_args)

        data_to_display = None
        if data is not None:
            if isinstance(data, list):
                data_to_display = map(self._get_data_to_display, data)
            elif isinstance(data, dict):
                data_to_display = self._get_data_to_display(data)

        if self.msg_to_display:
            self.app.stdout.write(self.msg_to_display)

        return (self.columns_names, data_to_display)


class ShowMixin(object):

    def operation(self, parsed_args=None):
        obj_id = getattr(parsed_args, 'id', None)
        return self._get_data_from_nailgun_entity(obj_id)
