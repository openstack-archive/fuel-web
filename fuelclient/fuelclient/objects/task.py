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

from time import sleep

from fuelclient.cli.error import DeployProgressError
from fuelclient.objects.base import BaseObject


class Task(BaseObject):

    class_api_path = "tasks/"
    instance_api_path = "tasks/{0}/"

    def delete(self, force=False):
        return self.connection.delete_request(
            "tasks/{0}/?force={1}".format(
                self.id,
                int(force),
            ))

    @property
    def progress(self):
        data = self.get_data()
        return data["progress"]

    @property
    def is_finished(self):
        return self.progress == 100

    def wait(self):
        while not self.is_finished:
            sleep(0.5)


class DeployTask(Task):

    def __init__(self, _id, env_id):
        from fuelclient.objects.environment import Environment
        super(DeployTask, self).__init__(_id)
        self.env = Environment(env_id)
        self.nodes = self.env.get_all_nodes()

    @classmethod
    def init_with_data(cls, data):
        return cls(data["id"], data["cluster"])

    @property
    def is_finished(self):
        return super(DeployTask, self).is_finished and all(
            map(lambda node: node.progress == 100, self.nodes)
        )

    def __iter__(self):
        return self

    def next(self):
        if not self.is_finished:
            sleep(1)
            deploy_task_data = self.get_data()
            if deploy_task_data["status"] == "error":
                raise DeployProgressError(deploy_task_data["message"])
            for node in self.nodes:
                node.update()
            return self.progress, self.nodes
        else:
            raise StopIteration


class SnapshotTask(Task):

    @classmethod
    def start_snapshot_task(cls):
        dump_task = cls.connection.put_request("logs/package", {})
        return cls(dump_task["id"])
