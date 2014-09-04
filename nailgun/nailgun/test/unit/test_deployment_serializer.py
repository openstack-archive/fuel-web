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
from nailgun.orchestrator import priority_serializers as ps


class TestCreateSerializer(BaseUnitTest):
    """Test cases for `create_serializer` function.
    """

    @mock.patch(
        'nailgun.orchestrator.deployment_serializers.extract_env_version',
        return_value='5.0')
    def test_retreiving_ha_for_5_0(self, _):
        cluster = mock.MagicMock(is_ha_mode=True)
        self.assertTrue(
            isinstance(
                ds.create_serializer(cluster),
                ds.DeploymentHASerializer))

    @mock.patch(
        'nailgun.orchestrator.deployment_serializers.extract_env_version',
        return_value='5.0')
    def test_retreiving_multinode_for_5_0(self, _):
        cluster = mock.MagicMock(is_ha_mode=False)
        self.assertTrue(
            isinstance(
                ds.create_serializer(cluster),
                ds.DeploymentMultinodeSerializer))

    @mock.patch(
        'nailgun.orchestrator.deployment_serializers.extract_env_version',
        return_value='5.1')
    def test_retreiving_ha_for_5_1(self, _):
        cluster = mock.MagicMock(is_ha_mode=True)
        self.assertTrue(
            isinstance(
                ds.create_serializer(cluster), ds.DeploymentHASerializer51))

    @mock.patch(
        'nailgun.orchestrator.deployment_serializers.extract_env_version',
        return_value='5.1')
    def test_retreiving_multinode_for_5_1(self, _):
        cluster = mock.MagicMock(is_ha_mode=False)
        self.assertTrue(
            isinstance(
                ds.create_serializer(cluster),
                ds.DeploymentMultinodeSerializer51))

    @mock.patch(
        'nailgun.orchestrator.deployment_serializers.extract_env_version',
        return_value='9999.0')
    def test_unsupported_serializer(self, _):
        cluster = mock.MagicMock(is_ha_mode=True)
        self.assertRaises(
            errors.UnsupportedSerializer, ds.create_serializer, cluster)

    @mock.patch(
        'nailgun.orchestrator.deployment_serializers.extract_env_version',
        return_value='5.0')
    def test_regular_priority_serializer_ha(self, _):
        cluster = mock.MagicMock(is_ha_mode=True, pending_release_id=None)
        prio = ds.create_serializer(cluster).priority

        self.assertTrue(isinstance(prio, ps.PriorityHASerializer50))

    @mock.patch(
        'nailgun.orchestrator.deployment_serializers.extract_env_version',
        return_value='5.0')
    def test_regular_priority_serializer_mn(self, _):
        cluster = mock.MagicMock(is_ha_mode=False, pending_release_id=None)
        prio = ds.create_serializer(cluster).priority

        self.assertTrue(isinstance(prio, ps.PriorityMultinodeSerializer50))

    @mock.patch(
        'nailgun.orchestrator.deployment_serializers.extract_env_version',
        return_value='5.0')
    def test_patching_priority_serializer_ha(self, _):
        cluster = mock.MagicMock(is_ha_mode=True, pending_release_id=42)
        prio = ds.create_serializer(cluster).priority

        self.assertTrue(isinstance(prio, ps.PriorityHASerializerPatching))

    @mock.patch(
        'nailgun.orchestrator.deployment_serializers.extract_env_version',
        return_value='5.0')
    def test_patching_priority_serializer_mn(self, _):
        cluster = mock.MagicMock(is_ha_mode=False, pending_release_id=42)
        prio = ds.create_serializer(cluster).priority

        self.assertTrue(
            isinstance(prio, ps.PriorityMultinodeSerializerPatching))
