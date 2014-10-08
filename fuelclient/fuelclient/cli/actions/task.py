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
from fuelclient.cli.actions.base import check_all
import fuelclient.cli.arguments as Args
from fuelclient.cli.arguments import group
from fuelclient.cli.formatting import format_table
from fuelclient.objects.task import Task


class TaskAction(Action):
    """Show tasks
    """
    action_name = "task"

    def __init__(self):
        super(TaskAction, self).__init__()
        self.args = [
            group(
                Args.get_list_arg("List all tasks"),
                Args.get_delete_arg("Delete task with some task-id.")
            ),
            Args.get_force_arg("Force deletion"),
            Args.get_task_arg("Task id.")
        ]
        self.flag_func_map = (
            ("delete", self.delete),
            (None, self.list)
        )

    @check_all("task")
    def delete(self, params):
        """To delete some tasks:
                fuel task delete --task-id 1,2,3

           To delete some tasks forcefully (without considering their state):
                fuel task delete -f --tid 1,6
        """
        tasks = Task.get_by_ids(params.task)
        delete_response = map(
            lambda task: task.delete(force=params.force),
            tasks
        )
        self.serializer.print_to_output(
            delete_response,
            "Tasks with id's {0} deleted."
            .format(', '.join(map(str, params.task)))
        )

    def list(self, params):
        """To display all tasks:
                fuel task

           To  display tasks with some ids:
                fuel task --tid 1,2,3
        """
        acceptable_keys = ("id", "status", "name",
                           "cluster", "progress", "uuid")
        if params.task:
            tasks_data = map(
                Task.get_fresh_data,
                Task.get_by_ids(params.task)
            )
        else:
            tasks_data = Task.get_all_data()
        self.serializer.print_to_output(
            tasks_data,
            format_table(tasks_data, acceptable_keys=acceptable_keys)
        )
