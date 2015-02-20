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

from operator import methodcaller
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
        return self.get_fresh_data()["progress"]

    @property
    def status(self):
        return self.get_fresh_data()["status"]

    @property
    def is_finished(self):
        return self.status in ("ready", "error")

    def wait(self):
        while not self.is_finished:
            sleep(0.5)


class DeployTask(Task):

    def __init__(self, obj_id, env_id):
        from fuelclient.objects.environment import Environment
        super(DeployTask, self).__init__(obj_id)
        self.env = Environment(env_id)
        self.nodes = self.env.get_all_nodes()

    @classmethod
    def init_with_data(cls, data):
        return cls(data["id"], data["cluster"])

    @property
    def not_finished_nodes(self):
        return filter(
            lambda n: not n.is_finished(latest=False),
            self.nodes
        )

    @property
    def is_finished(self):
        return super(DeployTask, self).is_finished and all(
            map(
                methodcaller("is_finished"),
                self.not_finished_nodes
            )
        )

    def __iter__(self):
        return self

    def next(self):
        if not self.is_finished:
            sleep(1)
            deploy_task_data = self.get_fresh_data()
            if deploy_task_data["status"] == "error":
                raise DeployProgressError(deploy_task_data["message"])
            for node in self.not_finished_nodes:
                node.update()
            return self.progress, self.nodes
        else:
            raise StopIteration


class SnapshotTask(Task):

    @classmethod
    def start_snapshot_task(cls, conf):
        dump_task = cls.connection.put_request("logs/package", conf)
        return cls(dump_task["id"])

    @classmethod
    def get_default_config(cls):
        return cls.connection.get_request("logs/package/config/default/")
