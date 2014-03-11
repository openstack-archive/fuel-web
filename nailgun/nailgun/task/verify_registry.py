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

from nailgun.task import manager


class TaskManagerRegistry(object):

    _registry = {}

    def __init__(self):
        for cls in manager.TaskManager.__subclasses__():
            if hasattr(cls, 'task_name'):
                self._registry[cls.task_name] = cls

    def get_task_manager(self, task_name):
        return self._registry.get(task_name, None)

    @classmethod
    def has_task_manager(self, task_name):
        return task_name in self._registry

    @classmethod
    def available_managers(self):
        return self._registry.keys()


registry = TaskManagerRegistry()
