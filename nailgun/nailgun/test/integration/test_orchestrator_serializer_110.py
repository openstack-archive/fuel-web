# -*- coding: utf-8 -*-

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

from nailgun import consts
from nailgun.orchestrator import deployment_serializers
from nailgun.test.integration import test_orchestrator_serializer_100


class TestSerializer110Mixin(object):
    env_version = 'ocata-11.0'
    task_deploy = True
    dpdk_bridge_provider = consts.NEUTRON_L23_PROVIDERS.dpdkovs

    @classmethod
    def create_serializer(cls, cluster):
        return deployment_serializers.DeploymentLCMSerializer110()

    @classmethod
    def _get_serializer(cluster):
        return deployment_serializers.DeploymentLCMSerializer110()

    @staticmethod
    def _get_plugins_names(plugins):
        """Plugins names for LCM serializers

        Single out <name> since plugin data may contain
        <scripts>, <repositories>, <whatever> as well.

        :param nodes: array of plugins data
        :returns: singled out names of plugins
        """
        return [plugin['name'] for plugin in plugins]


class TestNetworkDeploymentSerializer110(
    TestSerializer110Mixin,
    test_orchestrator_serializer_100.TestNetworkDeploymentSerializer100
):
    pass


class TestSerializeInterfaceDriversData110(
    TestSerializer110Mixin,
    test_orchestrator_serializer_100.TestSerializeInterfaceDriversData100
):
    pass
