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
from fuelclient.cli.formatting import download_snapshot_with_progress_bar
from fuelclient.objects.task import SnapshotTask


class SnapshotAction(Action):
    """Generate and download snapshot.
    """
    action_name = "snapshot"

    def __init__(self):
        super(SnapshotAction, self).__init__()
        self.args = (
            Args.get_dir_arg("Directory to which download snapshot."),
        )
        self.flag_func_map = (
            (None, self.get_snapshot),
        )

    def get_snapshot(self, params):
        """To download diagnostic snapshot:
                fuel snapshot

            To download diagnostic snapshot to specific directory:
                fuel snapshot --dir path/to/directory
        """
        snapshot_task = SnapshotTask.start_snapshot_task()
        self.serializer.print_to_output(
            snapshot_task.data,
            "Generating dump..."
        )
        snapshot_task.wait()
        download_snapshot_with_progress_bar(
            snapshot_task.connection.root + snapshot_task.data["message"],
            directory=params.dir
        )
