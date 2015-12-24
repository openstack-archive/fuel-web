
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


from nailgun.api.v1.validators.network import NetAssignmentValidator
from nailgun.test.base import BaseValidatorTest

class BaseNetAssignmentValidatorTest(BaseValidatorTest):
    validator = NetAssignmentValidator.verify_data_correctness

class TestNetAssignmentValidator(BaseNetAssignmentValidatorTest):

    def test_verify_data_correctness_when_node_in_cluster(self):
        node = self.env.create(
            nodes_kwargs=[{
                'roles': ['controller'],
                'api': True}])
        node_data = self.env.nodes[0]
        data = { 'id': node_data['id'], 'interfaces': node_data['meta']['interfaces'] }
        self.validator(node_data)

    def test_verify_data_correctness_when_node_not_in_cluster(self):
        node = self.env.create_node()
        node_data = self.env.nodes[0]
        data = { 'id': node_data['id'], 'interfaces': node_data['meta']['interfaces'] }
        self.validator(node_data)
