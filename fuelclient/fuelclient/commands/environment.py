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

from fuelclient import objects


class EnvList(lister.Lister):
    """Show list of all avaliable envrionments
    """
    columns_names = ("id",
                     "status",
                     "name",
                     "mode",
                     "release_id",
                     "changes",
                     "pending_release_id")

    def take_action(self, parsed_args):

        env = objects.Environment.get_all_data()

        get_data_to_display = lambda elem: \
            [elem[field] for field in self.acceptable_keys]

        data = (get_data_to_display(elem) for elem in env)

        return (self.columns_names, data)


class EnvDelete(command.Command):
    """Delete environment with given id
    """

    def take_action(self, parsed_args):
        env = objects.Environment(parsed_args.env, params=parsed_args)
        data = env.delete()

        self.app.stdout.write('Environment with id={0} was deleted'
                              .format(data['id']))


class EnvUpdate(show.ShowOne):
    """Change given attributes for env
    """

    columns_names = ('mode', 'name', 'pending_release_id')

    def take_action(self, parsed_args):

        env = objects.Environment(parsed_args.env, params=parsed_args)

        msg = ("Following attributes are changed for "
               "the environment: \n")

        # attributes for env to update
        update_kwargs = dict(
            [
                (arg_name, arg_value) for arg_name, arg_value in
                parsed_args.__dict__.iteritems()
                if arg_name in self.columns_names
            ]
        )

        # execute update itself
        env.set(update_kwargs)

        # pring to stdout message
        self.app.stdout.write(msg)
        return(update_kwargs.iterkeys(), update_kwargs.iteritems)
