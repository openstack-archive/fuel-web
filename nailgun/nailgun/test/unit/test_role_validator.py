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

from nailgun.api.v1.validators.json_schema import base_types
from nailgun.api.v1.validators.json_schema import role
from nailgun.api.v1.validators.role import RoleValidator
from nailgun.errors import errors
from nailgun.test import base


class TestRoleVolumeAllocationsValidationBySchema(base.BaseValidatorUnitTest):
    invalid_data = [1, 'some_string', dict(), list()]
    ids = ['os', 'image', 'vm', 'cinder', 'ceph', 'cephjournal', 'mongo']
    allocation_sizes = ['all', 'min', 'full-disk']

    def assertInvalidData(self, volumes):
        self.assertRaises(
            errors.InvalidData, RoleValidator.validate_schema,
            volumes, role.VOLUME_ALLOCATIONS)

    def test_properties_allocate_size(self):
        for size in self.allocation_sizes:
            volumes = [{'allocate_size': size, 'id': self.ids[0]}]
            RoleValidator.validate_schema(volumes, role.VOLUME_ALLOCATIONS)

        for size in self.invalid_data:
            volumes = [{'allocate_size': size, 'id': self.ids[0]}]
            self.assertInvalidData(volumes)

    def test_properties_id(self):
        for i in self.ids:
            volumes = [{'allocate_size': self.allocation_sizes[0], 'id': i}]
            RoleValidator.validate_schema(volumes, role.VOLUME_ALLOCATIONS)

    def test_full_restriction(self):
        full_restriction = {'condition': "some_string"}
        RoleValidator.validate_schema(full_restriction,
                                      base_types._FULL_RESTRICTION)

    def test_restrictions(self):
        restrictions = ["conidtion", {'condition': "some condition"}]
        RoleValidator.validate_schema(restrictions, base_types.RESTRICTIONS)

    def test_meta_info(self):
        meta = {'name': 'Some Name', 'description': 'Some Description'}
        RoleValidator.validate_schema(meta, role.ROLE_META_INFO)
