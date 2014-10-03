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

from nailgun.api.v1.validators.assignment import NodeAssignmentValidator
from nailgun.errors import errors
from nailgun.test.base import BaseUnitTest


class TestAssignmentValidator(BaseUnitTest):
    def setUp(self):
        self.models = {
            'settings': {
                'parent': {
                    'child': {
                        'value': 1
                    }
                }
            }
        }

    def test_check_roles_requirement(self):
        roles = ['test']
        roles_metadata = {
            'test': {
                'depends': [
                    {
                        'condition': 'settings:parent.child.value == 1',
                        'warning': 'error'
                    }
                ]
            }
        }

        NodeAssignmentValidator.check_roles_requirement(roles,
                                                        roles_metadata,
                                                        self.models)

        roles = ['test']
        roles_metadata = {
            'test': {
                'depends': [
                    {
                        'condition': "settings:parent.child.value != 'x'",
                        'warning': 'error'
                    }
                ]
            }
        }

        NodeAssignmentValidator.check_roles_requirement(roles,
                                                        roles_metadata,
                                                        self.models)

    def test_check_roles_requirement_failed(self):
        roles = ['test']

        # wrong child value
        with self.assertRaises(errors.InvalidData):
            roles_metadata = {
                'test': {
                    'depends': [
                        {
                            'condition': 'settings:parent.child.value == 0',
                            'warning': 'error'
                        }
                    ]
                }
            }

            NodeAssignmentValidator.check_roles_requirement(roles,
                                                            roles_metadata,
                                                            self.models)
