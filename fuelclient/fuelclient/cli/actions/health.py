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
from fuelclient.cli.error import exit_with_error
from fuelclient.cli.formatting import format_table
from fuelclient.cli.formatting import print_health_check
from fuelclient.objects.environment import Environment


class HealthCheckAction(Action):
    """Run health check on environment
    """
    action_name = "health"

    _allowed_statuses = (
        'error',
        'operational',
        'update_error',
    )

    def __init__(self):
        super(HealthCheckAction, self).__init__()
        self.args = (
            Args.get_env_arg(required=True),
            Args.get_list_arg("List all available checks"),
            Args.get_force_arg("Forced test run"),
            Args.get_check_arg("Run check for some testset.")
        )

        self.flag_func_map = (
            ("check", self.check),
            (None, self.list)
        )

    def check(self, params):
        """To run some health checks:
                fuel --env 1 health --check smoke,sanity
        """
        env = Environment(params.env)

        if env.status not in self._allowed_statuses and not params.force:
            exit_with_error(
                "Environment is not ready to run health check "
                "because it is in {0} state. "
                "Health check is likely to fail because of "
                "this. Use --force flag to proceed anyway.". format(env.status)
            )

        if env.is_customized and not params.force:
            exit_with_error(
                "Environment deployment facts were updated. "
                "Health check is likely to fail because of "
                "that. Use --force flag to proceed anyway."
            )
        test_sets_to_check = params.check or set(
            ts["id"] for ts in env.get_testsets())
        env.run_test_sets(test_sets_to_check)
        tests_state = env.get_state_of_tests()
        self.serializer.print_to_output(
            tests_state,
            env,
            print_method=print_health_check
        )

    def list(self, params):
        """To list all health check test sets:
                fuel health
            or:
                fuel --env 1 health --list
        """
        env = Environment(params.env)
        test_sets = env.get_testsets()
        self.serializer.print_to_output(
            test_sets,
            format_table(test_sets)
        )
