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

from nailgun.api.validators.assignment import NodeAssignmentValidator
from nailgun.errors import errors
from nailgun.test.base import BaseUnitTest


class TestAssignmentValidator(BaseUnitTest):
    def setUp(self):
        self.settings = {'parent': {
                         'child': {
                         'value': 1
                         }}}

    def test_search_in_settings(self):
        pattern = 'parent.child.value'
        result = NodeAssignmentValidator._search_in_settings(self.settings,
                                                             pattern)
        self.assertEquals(result, 1)

    def test_search_in_settings_non_exisxt(self):
        pattern = 'parent.fake.value'
        result = NodeAssignmentValidator._search_in_settings(self.settings,
                                                             pattern)
        self.assertEquals(result, None)

    def test_check_roles_requirement(self):
        roles = ['test']
        roles_metadata = {'test':
                         {'depends':
                          [{'condition': {'setting:parent.child.value': 1},
                           'warning': 'error'}]}}
        try:
            NodeAssignmentValidator.check_roles_requirement(roles,
                                                            roles_metadata,
                                                            self.settings)
        except errors.InvalidData as e:
            self.fail('check_roles_requirement raised exception: {0}'.format(
                e.message))

    def test_check_roles_requirement_failed(self):
        roles = ['test']

        with self.assertRaises(errors.InvalidData):
            roles_metadata = {'test':
                              {'depends':
                              [{'condition': {'setting:parent.child.value': 0},
                                'warning': 'error'}]}}
            NodeAssignmentValidator.check_roles_requirement(roles,
                                                            roles_metadata,
                                                            self.settings)

        with self.assertRaises(errors.InvalidData):
            roles_metadata = {'test':
                              {'depends':
                               [{'condition': {'parent.child.value': 0},
                               'warning': 'error'}]}}
            NodeAssignmentValidator.check_roles_requirement(roles,
                                                            roles_metadata,
                                                            self.settings)

    def test_check_roles_for_conflicts(self):
        roles_metadata = {
            'role_1': {'conflicts': []},
            'role_2': {'conflicts': ['role_1', 'role_3']}
        }
        NodeAssignmentValidator.check_roles_for_conflicts(
            [], roles_metadata)
        NodeAssignmentValidator.check_roles_for_conflicts(
            ['unknown_role'], roles_metadata)
        NodeAssignmentValidator.check_roles_for_conflicts(
            ['role_1'], roles_metadata)
        NodeAssignmentValidator.check_roles_for_conflicts(
            ['role_3'], roles_metadata)
        self.assertRaises(
            errors.InvalidData,
            NodeAssignmentValidator.check_roles_for_conflicts,
            ['role_1', 'role_2'], roles_metadata
        )
