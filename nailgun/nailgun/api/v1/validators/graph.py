# -*- coding: utf-8 -*-
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

from nailgun.api.v1.validators.base import BasicValidator
from nailgun.api.v1.validators.json_schema import tasks
from nailgun.errors import errors
from nailgun.orchestrator import deployment_graph


class GraphTasksValidator(BasicValidator):

    @classmethod
    def validate_update(cls, data, instance):
        parsed = cls.validate(data)
        cls.validate_schema(parsed, tasks.TASKS_SCHEMA)
        graph = deployment_graph.DeploymentGraph()
        graph.add_tasks(parsed)
        if not graph.is_acyclic():
            raise errors.InvalidData(
                "Tasks can not be processed because it contains cycles in it.")
        return parsed
