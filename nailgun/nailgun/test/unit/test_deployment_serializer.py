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

import mock

from nailgun.errors import errors
from nailgun.test.base import BaseUnitTest

from nailgun.orchestrator import deployment_serializers as ds


class TestGetSerializer(BaseUnitTest):
    """Test cases for `get_serializer` function.
    """

    @mock.patch(
        'nailgun.orchestrator.deployment_serializers.extract_env_version',
        return_value='5.0')
    def test_retreiving_ha_for_5_0(self, _):
        cluster = mock.MagicMock(is_ha_mode=True)
        self.assertTrue(
            ds.get_serializer(cluster) is ds.DeploymentHASerializer)

    @mock.patch(
        'nailgun.orchestrator.deployment_serializers.extract_env_version',
        return_value='5.0')
    def test_retreiving_multinode_for_5_0(self, _):
        cluster = mock.MagicMock(is_ha_mode=False)
        self.assertTrue(
            ds.get_serializer(cluster) is ds.DeploymentMultinodeSerializer)

    @mock.patch(
        'nailgun.orchestrator.deployment_serializers.extract_env_version',
        return_value='5.1')
    def test_retreiving_ha_for_5_1(self, _):
        cluster = mock.MagicMock(is_ha_mode=True)
        self.assertTrue(
            ds.get_serializer(cluster) is ds.DeploymentHASerializer51)

    @mock.patch(
        'nailgun.orchestrator.deployment_serializers.extract_env_version',
        return_value='5.1')
    def test_retreiving_multinode_for_5_1(self, _):
        cluster = mock.MagicMock(is_ha_mode=False)
        self.assertTrue(
            ds.get_serializer(cluster) is ds.DeploymentMultinodeSerializer51)

    @mock.patch(
        'nailgun.orchestrator.deployment_serializers.extract_env_version',
        return_value='9999.0')
    def test_unsupported_serializer(self, _):
        cluster = mock.MagicMock(is_ha_mode=True)
        self.assertRaises(
            errors.UnsupportedSerializer, ds.get_serializer, cluster)
