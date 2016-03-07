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

from nailgun.orchestrator.neutron_serializers import \
    NeutronNetworkDeploymentSerializer90
from nailgun.orchestrator.neutron_serializers import \
    NeutronNetworkTemplateSerializer90

from nailgun.test.integration import test_orchestrator_serializer_80


class TestSerializer90Mixin(object):
    env_version = "liberty-9.0"
    task_deploy = True


class TestBlockDeviceDevicesSerialization90(
    TestSerializer90Mixin,
    test_orchestrator_serializer_80.TestBlockDeviceDevicesSerialization80
):
    pass


class TestDeploymentAttributesSerialization90(
    TestSerializer90Mixin,
    test_orchestrator_serializer_80.TestDeploymentAttributesSerialization80
):
    pass


class TestDeploymentHASerializer90(
    TestSerializer90Mixin,
    test_orchestrator_serializer_80.TestDeploymentHASerializer80
):
    def test_glance_properties(self):
        self.check_no_murano_data()


class TestDeploymentTasksSerialization90(
    TestSerializer90Mixin,
    test_orchestrator_serializer_80.TestDeploymentTasksSerialization80
):
    pass


class TestMultiNodeGroupsSerialization90(
    TestSerializer90Mixin,
    test_orchestrator_serializer_80.TestMultiNodeGroupsSerialization80
):
    pass


class TestNetworkTemplateSerializer90(
    TestSerializer90Mixin,
    test_orchestrator_serializer_80.TestNetworkTemplateSerializer80
):
    legacy_serializer = NeutronNetworkDeploymentSerializer90
    template_serializer = NeutronNetworkTemplateSerializer90


class TestSerializeInterfaceDriversData90(
    TestSerializer90Mixin,
    test_orchestrator_serializer_80.TestSerializeInterfaceDriversData80
):
    pass
