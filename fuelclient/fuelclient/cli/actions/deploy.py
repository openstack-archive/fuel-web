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
from fuelclient.cli.formatting import print_deploy_progress


class DeployChangesAction(Action):
    """Deploy changes to environments
    """
    action_name = "deploy-changes"

    def __init__(self):
        super(DeployChangesAction, self).__init__()
        self.args = (
            Args.get_env_arg(required=True),
        )

        self.flag_func_map = (
            (None, self.deploy_changes),
        )

    def deploy_changes(self, params):
        """To deploy all applied changes to some environment:
            fuel --env 1 deploy-changes
        """
        from fuelclient.objects.environment import Environment
        env = Environment(params.env)
        deploy_task = env.deploy_changes()
        self.serializer.print_to_output(
            deploy_task.data,
            deploy_task,
            print_method=print_deploy_progress)
