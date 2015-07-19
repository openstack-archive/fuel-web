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

import mock

from oslo_serialization import jsonutils

from nailgun.errors import errors
from nailgun.test import base

from .. import validators
from . import EXTENSION


class TestClusterUpgradeValidator(base.BaseTestCase):
    validator = validators.ClusterUpgradeValidator

    def test_validate_release_upgrade(self):
        orig_release = mock.MagicMock()
        orig_release.__ge__.return_value = False
        new_release = mock.Mock(is_deployable=True)
        self.validator.validate_release_upgrade(orig_release,
                                                new_release)
        orig_release.__ge__.assert_called_once_with(new_release)

    def test_validate_release_upgrade_deprecated_release(self):
        orig_release = mock.MagicMock()
        new_release = mock.Mock(is_deployable=False)
        msg = "^Upgrade.*release is deprecated and cannot be installed\.$"
        with self.assertRaisesRegexp(errors.InvalidData, msg):
            self.validator.validate_release_upgrade(orig_release,
                                                    new_release)

    def test_validate_release_upgrade_to_older_release(self):
        orig_release = mock.MagicMock()
        orig_release.__ge__.return_value = True
        new_release = mock.Mock(is_deployable=True)
        msg = "^Upgrade.*release is equal or lower than the release of the " \
              "original cluster\.$"
        with self.assertRaisesRegexp(errors.InvalidData, msg):
            self.validator.validate_release_upgrade(orig_release,
                                                    new_release)

    @mock.patch(EXTENSION + "validators.objects.ClusterCollection")
    def test_validate_cluster_name(self, mock_collection):
        mock_collection.filter_by.return_value.first.return_value = None
        self.validator.validate_cluster_name("cluster-42")
        mock_collection.filter_by.assert_called_once_with(None,
                                                          name="cluster-42")

    @mock.patch(EXTENSION + "validators.objects.ClusterCollection")
    def test_validate_cluster_name_already_exists(self, mock_collection):
        msg = "^Environment with this name already exists\.$"
        with self.assertRaisesRegexp(errors.AlreadyExists, msg):
            self.validator.validate_cluster_name("cluster-42")
        mock_collection.filter_by.assert_called_once_with(None,
                                                          name="cluster-42")

    @mock.patch(EXTENSION + "objects.relations.UpgradeRelationObject")
    def test_validate_cluster_status(self, mock_relation):
        mock_relation.is_cluster_in_upgrade.return_value = False
        cluster = mock.Mock(id=42)
        self.validator.validate_cluster_status(cluster)
        mock_relation.is_cluster_in_upgrade.assert_called_once_with(42)

    @mock.patch(EXTENSION + "objects.relations.UpgradeRelationObject")
    def test_validate_cluster_status_invalid(self, mock_relation):
        mock_relation.is_cluster_in_upgrade.return_value = True
        cluster = mock.Mock(id=42)
        msg = "^Upgrade.*cluster is already involed in the upgrade routine\.$"
        with self.assertRaisesRegexp(errors.InvalidData, msg):
            self.validator.validate_cluster_status(cluster)
        mock_relation.is_cluster_in_upgrade.assert_called_once_with(42)

    @mock.patch.object(validator, "validate_release_upgrade")
    @mock.patch(EXTENSION + "validators.adapters.NailgunReleaseAdapter")
    @mock.patch(EXTENSION + "validators.objects.Release.get_by_uid")
    @mock.patch.object(validator, "validate_cluster_name")
    @mock.patch.object(validator, "validate_cluster_status")
    @mock.patch(EXTENSION + "validators.adapters.NailgunClusterAdapter")
    def test_validate(self,
                      mock_cluster_adapter,
                      mock_v_cluster_status,
                      mock_v_cluster_name,
                      mock_get_release,
                      mock_release_adapter,
                      mock_v_release_upgrade):
        data = jsonutils.dumps({
            "name": "cluster-42",
            "release_id": 24,
        })
        cluster_db = mock.Mock()
        mock_cluster_adapter.return_value = cluster = mock.Mock(id=42)
        mock_get_release.return_value = release_db = mock.Mock()
        mock_release_adapter.return_value = release = mock.Mock()

        self.validator.validate(data, cluster_db)

        mock_cluster_adapter.assert_called_once_with(cluster_db)
        mock_v_cluster_status.assert_called_once_with(cluster)
        mock_v_cluster_name.assert_called_once_with("cluster-42")
        mock_get_release.assert_called_once_with(24, fail_if_not_found=True)
        mock_release_adapter.assert_called_once_with(release_db)
        mock_v_release_upgrade.assert_called_once_with(cluster.release,
                                                       release)

    @mock.patch.object(validator, "validate_release_upgrade")
    @mock.patch(EXTENSION + "validators.adapters.NailgunReleaseAdapter")
    @mock.patch(EXTENSION + "validators.objects.Release.get_by_uid")
    @mock.patch.object(validator, "validate_cluster_name")
    @mock.patch.object(validator, "validate_cluster_status")
    @mock.patch(EXTENSION + "validators.adapters.NailgunClusterAdapter")
    def test_validate_invalid_data(self, mock_cluster_adapter, *args):
        data = "{}"
        mock_cluster_adapter.return_value = cluster = mock.Mock(id=42)
        with self.assertRaises(errors.InvalidData):
            self.validator.validate(data, cluster)

class TestNodeReassignValidator(base.BaseTestCase):
    validator = validators.NodeReassignValidator

    @mock.patch(EXTENSION + "validators.adapters.NailgunNodeAdapter."
        "get_by_uid")
    def test_validate_node_not_found(self, mock_gbu):
        mock_gbu.return_value = mock.Mock(node=None)
        with self.assertRaises(errors.ObjectNotFound):
            self.validator.validate_node(42)

    @mock.patch(EXTENSION + "validators.adapters.NailgunNodeAdapter."
        "get_by_uid")
    def test_validate_node_wrong_status(self, mock_gbu):
        mock_gbu.return_value = mock.Mock(status='wrong_state')
        with self.assertRaises(errors.InvalidData):
            self.validator.validate_node(42)
