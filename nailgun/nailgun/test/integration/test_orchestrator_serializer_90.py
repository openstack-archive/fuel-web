# -*- coding: utf-8 -*-

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

from nailgun.test.integration.test_orchestrator_serializer_80 import \
    TestDeploymentHASerializer80


class TestDeploymentHASerializer90(TestDeploymentHASerializer80):
    env_version = "liberty-9.0"

    def check_generate_test_vm_image_data(self):
        glance_properties = self.serializer.generate_test_vm_image_data(
            self.env.nodes[0])['test_vm_image']['glance_properties']
        self.assertNotIn('murano_image_info', glance_properties)
