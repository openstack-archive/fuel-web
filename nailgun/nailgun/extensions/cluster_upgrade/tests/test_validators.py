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

from nailgun import consts
from nailgun.errors import errors
from nailgun.settings import settings
from nailgun.test import base

from nailgun.extensions.cluster_upgrade.objects import relations
from nailgun.extensions.cluster_upgrade.tests import base as tests_base
from nailgun.extensions.cluster_upgrade.tests import EXTENSION
from nailgun.extensions.cluster_upgrade import validators


class TestClusterUpgradeValidator(tests_base.BaseCloneClusterTest):
    validator = validators.ClusterUpgradeValidator

    def test_validate_release_upgrade(self):
        self.validator.validate_release_upgrade(self.release_61,
                                                self.release_80)

    @mock.patch.dict(settings.VERSION, {'feature_groups': []})
    def test_validate_release_upgrade_deprecated_release(self):
        release_511 = self.env.create_release(
            operating_system=consts.RELEASE_OS.ubuntu,
            version="2014.1.3-5.1.1",
            state=consts.RELEASE_STATES.manageonly
        )
        msg = "^Upgrade to the given release \({0}\).*is deprecated and " \
              "cannot be installed\.$".format(self.release_61.id)
        with self.assertRaisesRegexp(errors.InvalidData, msg):
            self.validator.validate_release_upgrade(release_511,
                                                    self.release_61)

    def test_validate_release_upgrade_to_older_release(self):
        self.release_61.state = consts.RELEASE_STATES.available
        msg = "^Upgrade to the given release \({0}\).*release is equal or " \
              "lower than the release of the original cluster\.$" \
              .format(self.release_61.id)
        with self.assertRaisesRegexp(errors.InvalidData, msg):
            self.validator.validate_release_upgrade(self.release_80,
                                                    self.release_61)

    def test_validate_cluster_name(self):
        self.validator.validate_cluster_name("cluster-42")

    def test_validate_cluster_name_already_exists(self):
        msg = "^Environment with this name '{0}' already exists\.$"\
              .format(self.cluster_61.name)
        with self.assertRaisesRegexp(errors.AlreadyExists, msg):
            self.validator.validate_cluster_name(self.cluster_61.name)

    def test_validate_cluster_status(self):
        self.validator.validate_cluster_status(self.cluster_61)

    def test_validate_cluster_status_invalid(self):
        cluster_80 = self.env.create_cluster(
            api=False,
            release_id=self.release_80.id,
        )
        relations.UpgradeRelationObject.create_relation(self.cluster_61.id,
                                                        cluster_80.id)
        msg = "^Upgrade is not possible because of the original cluster " \
              "\({0}\) is already involved in the upgrade routine\.$" \
              .format(self.cluster_61.id)
        with self.assertRaisesRegexp(errors.InvalidData, msg):
            self.validator.validate_cluster_status(self.cluster_61)

    def test_validate(self):
        data = jsonutils.dumps(self.data)
        self.validator.validate(data, self.cluster_61)

    def test_validate_invalid_data(self):
        data = "{}"
        with self.assertRaises(errors.InvalidData):
            self.validator.validate(data, self.cluster_61)


class TestNodeReassignValidator(base.BaseTestCase):
    validator = validators.NodeReassignValidator

    @mock.patch(EXTENSION + "validators.adapters.NailgunNodeAdapter."
                "get_by_uid")
    def test_validate_node_not_found(self, mock_gbu):
        mock_gbu.return_value = None
        with self.assertRaises(errors.ObjectNotFound):
            self.validator.validate_node(42)

    @mock.patch(EXTENSION + "validators.adapters.NailgunNodeAdapter."
                "get_by_uid")
    def test_validate_node_wrong_status(self, mock_gbu):
        mock_gbu.return_value = mock.Mock(status='wrong_state')
        with self.assertRaises(errors.InvalidData):
            self.validator.validate_node(42)

    @mock.patch(EXTENSION + "validators.adapters.NailgunNodeAdapter."
                "get_by_uid")
    def test_validate_node_wrong_error_type(self, mock_gbu):
        mock_gbu.return_value = mock.Mock(status='error',
                                          error_type='wrong')
        with self.assertRaises(errors.InvalidData):
            self.validator.validate_node(42)

    def test_validate_node_cluster(self):
        node = mock.Mock(id=42, cluster_id=42)
        cluster = mock.Mock(id=42)
        with self.assertRaises(errors.InvalidData):
            self.validator.validate_node_cluster(node, cluster)

    def test_validate_empty_data(self):
        cluster = self.env.create_cluster(api=False)
        node = self.env.create_node(cluster_id=cluster.id,
                                    roles=["compute"],
                                    status="ready")
        msg = "^'node_id' is a required property"
        with self.assertRaisesRegexp(errors.InvalidData, msg):
            self.validator.validate("{}", node)

    def test_validate_empty_body(self):
        cluster = self.env.create_cluster(api=False)
        node = self.env.create_node(cluster_id=cluster.id,
                                    roles=["compute"],
                                    status="ready")
        msg = "^Empty request received$"
        with self.assertRaisesRegexp(errors.InvalidData, msg):
            self.validator.validate("", node)
