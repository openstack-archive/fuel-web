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

from nailgun.logger import logger
from nailgun.api.v1.validators.json_schema import master_node_settings


class MasterNodeSettingsValidator(BasicValidator):

    @classmethod
    def validate_update(cls, data, instance=None):
        data = cls.validate_json(data)

        if data.get("master_node_uid"):
            logger.warn(
                "Changing of master node uid is not allowed. "
                "It will be ignored",
            )

        cls.validate_schema(data, schema=master_node_settings.schema)

        return data
