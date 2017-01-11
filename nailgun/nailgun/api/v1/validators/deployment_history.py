#    Copyright 2016 Mirantis, Inc.
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
from nailgun import consts
from nailgun import errors


class DeploymentHistoryValidator(BasicValidator):

    @classmethod
    def validate_query(cls, nodes_ids, statuses, tasks_names):
        if not statuses:
            return

        if not statuses.issubset(set(consts.HISTORY_TASK_STATUSES)):
            raise errors.ValidationException(
                "Statuses parameter could be only: {}".format(
                    ", ".join(consts.HISTORY_TASK_STATUSES))
            )
