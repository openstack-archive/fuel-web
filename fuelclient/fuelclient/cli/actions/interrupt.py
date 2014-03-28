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


from fuelclient.cli.actions.base import Action
import fuelclient.cli.arguments as Args
from fuelclient.objects.environment import Environment


class InterruptAction(Action):

    def __init__(self):
        super(InterruptAction, self).__init__()
        self.args = [
            Args.get_env_arg(required=True)
        ]
        self.flag_func_map = (
            (None, self.interrupt),
        )

    def interrupt(self, params):
        """To {action_name} some environment:
                fuel --env 1 {action_name}
        """
        env = Environment(params.env)
        intercept_task = getattr(env, self.action_name)()
        self.serializer.print_to_output(
            intercept_task.data,
            "{0} task of environment with id={1} started. "
            "To check task status run 'fuel task -t {2}'.".format(
                self.action_name.title(),
                params.env,
                intercept_task.data["id"]
            )
        )


class StopAction(InterruptAction):
    """Stop deployment process for specific environment
    """
    action_name = "stop"


class ResetAction(InterruptAction):
    """Reset deployed process for specific environment
    """
    action_name = "reset"
