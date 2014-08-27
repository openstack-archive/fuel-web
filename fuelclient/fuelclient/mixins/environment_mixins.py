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
                     "net_provider")

    def get_data_to_display(self, data_elem):
        return [data_elem[field] for field in self.columns_names]


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

        data = env.set(update_kwargs)

        return data
