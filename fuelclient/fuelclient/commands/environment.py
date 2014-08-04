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

from fuelclient import objects


class EnvList(lister.Lister):
    """Show list of all avaliable envrionments
    """
    acceptable_keys = ("id",
                       "status",
                       "name",
                       "mode",
                       "release_id",
                       "changes",
                       "pending_release_id")

    def take_action(self, parsed_args):

        env = objects.Environment.get_all_data()

        columns_names = self.acceptable_keys

        get_needed_data = lambda data: \
            [data[field] for field in self.acceptable_keys]
        data = (get_needed_data(data) for data in env)

        return (
            columns_names,
            data
        )


class EnvDelete(command.Command):
    """Delete environment with given id
    """

    def take_action(self, parsed_args):
        env = objects.Environment(parsed_args.env, params=parsed_args)
        data = env.delete()

        self.app.stdout.write('Environment with id={0} was deleted'
                              .format(data['id']))


class EnvUpdate(command.Command):
    """Change given attributes for env
    """

    acceptable_params = ('mode', 'name', 'pending_release_id')

    def take_action(self, parsed_args):

        env = objects.Environment(parsed_args.env, params=parsed_args)

        # forming message for output and data structure for request body
        # TODO(aroma): make it less ugly
        msg_template = ("Following attributes are changed for "
                        "the environment: {env_attributes}")

        env_attributes = []
        update_kwargs = dict()
        for param_name in self.acceptable_params:
            attr_value = getattr(parsed_args, param_name, None)
            if attr_value:
                update_kwargs[param_name] = attr_value
                env_attributes.append(
                    ''.join([param_name, '=', six.text_type(attr_value)])
                )

        env.set(update_kwargs)
        env_attributes = ', '.join(env_attributes)

        self.app.stdout.write(
            msg_template.format(env_attributes=env_attributes)
        )
