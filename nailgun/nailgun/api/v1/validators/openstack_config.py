#    Copyright 2015 Mirantis, Inc.
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

from nailgun.api.v1.validators.json_schema import openstack_config as schema


class OpenstackConfigValidator(BasicValidator):

    # single_schema = schema.OPENSTACK_CONFIG
    # collection_schema = schema.OPENSTACK_CONFIG_COLLECTION

    @classmethod
    def validate(cls, data, instance=None):
        data = super(OpenstackConfigValidator, cls).validate(data)
        cls.validate_schema(data, schema.OPENSTACK_CONFIG)

        return data
