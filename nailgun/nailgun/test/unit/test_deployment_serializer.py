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

from nailgun.test.base import BaseUnitTest

from nailgun.orchestrator import deployment_serializers as ds


class TestGetSerializer(BaseUnitTest):
    """Test cases for `get_serializer_for_cluster` function"""

    def test_retreiving_ha_for_5_0(self):
        cluster = mock.MagicMock(is_ha_mode=True)
        cluster.release.environment_version = '5.0'
        self.assertIs(
            ds.get_serializer_for_cluster(cluster),
            ds.DeploymentHASerializer50)

    def test_retreiving_multinode_for_5_0(self):
        cluster = mock.MagicMock(is_ha_mode=False)
        cluster.release.environment_version = '5.0'
        self.assertIs(
            ds.get_serializer_for_cluster(cluster),
            ds.DeploymentMultinodeSerializer50)

    def test_retreiving_ha_for_5_1(self):
        cluster = mock.MagicMock(is_ha_mode=True)
        cluster.release.environment_version = '5.1'
        self.assertIs(
            ds.get_serializer_for_cluster(cluster),
            ds.DeploymentHASerializer51)

    def test_retreiving_multinode_for_5_1(self):
        cluster = mock.MagicMock(is_ha_mode=False)
        cluster.release.environment_version = '5.1'
        self.assertIs(
            ds.get_serializer_for_cluster(cluster),
            ds.DeploymentMultinodeSerializer51)

    def test_retreiving_ha_for_6_0(self):
        cluster = mock.MagicMock(is_ha_mode=True)
        cluster.release.environment_version = '6.0'
        self.assertIs(
            ds.get_serializer_for_cluster(cluster),
            ds.DeploymentHASerializer60)

    def test_retreiving_multinode_for_6_0(self):
        cluster = mock.MagicMock(is_ha_mode=False)
        cluster.release.environment_version = '6.0'
        self.assertIs(
            ds.get_serializer_for_cluster(cluster),
            ds.DeploymentMultinodeSerializer60)

    def test_retreiving_ha_for_6_1(self):
        cluster = mock.MagicMock(is_ha_mode=True)
        cluster.release.environment_version = '6.1'
        self.assertIs(
            ds.get_serializer_for_cluster(cluster),
            ds.DeploymentHASerializer61)

    def test_retreiving_multinode_for_6_1(self):
        cluster = mock.MagicMock(is_ha_mode=False)
        cluster.release.environment_version = '6.1'
        self.assertIs(
            ds.get_serializer_for_cluster(cluster),
            ds.DeploymentMultinodeSerializer61)

    def test_retreiving_ha_for_7_0(self):
        cluster = mock.MagicMock(is_ha_mode=True)
        cluster.release.environment_version = '7.0'
        self.assertIs(
            ds.get_serializer_for_cluster(cluster),
            ds.DeploymentHASerializer70)

    def test_retreiving_ha_for_8_0(self):
        cluster = mock.MagicMock(is_ha_mode=True)
        cluster.release.environment_version = '8.0'
        self.assertIs(
            ds.get_serializer_for_cluster(cluster),
            ds.DeploymentHASerializer80)

    def test_usage_of_latest_serializer_in_case_of_new_release(self):
        cluster = mock.MagicMock(is_ha_mode=True)
        cluster.release.environment_version = '9999.0'
        self.assertIs(
            ds.get_serializer_for_cluster(cluster),
            ds.DeploymentHASerializer90)
