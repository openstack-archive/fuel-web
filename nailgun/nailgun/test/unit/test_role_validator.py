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


from nailgun.api.v1.validators.json_schema import role
from nailgun.api.v1.validators.role import RoleValidator
from nailgun.test.base import BaseUnitTest


class TestNodeAssignmentValidator(BaseUnitTest):

    def test_allocate_volumes_validator(self):
        volumes = [{'allocate_size': 'all', 'id': 'os'}]
        RoleValidator.validate_schema(volumes, role.VOLUME_ALLOCATIONS)

    def test_meta_validator(self):
        meta = {'name': 'Some Name', 'description': 'Some Description'}
        RoleValidator.validate_schema(meta, role.ROLE_META_INFO)
