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

from oslo_serialization import jsonutils

from nailgun.utils import reverse

from . import base as tests_base


class TestClusterUpgradeHandler(tests_base.BaseCloneClusterTest):
    def test_clone(self):
        resp = self.app.post(
            reverse("ClusterUpgradeHandler",
                    kwargs={"cluster_id": self.cluster_61.id}),
            jsonutils.dumps(self.data),
            headers=self.default_headers)
        body = resp.json_body
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(body["name"],
                         "cluster-clone-{0}".format(self.cluster_61.id))
        self.assertEqual(body["release_id"], self.release_70.id)

    def test_clone_cluster_not_found_error(self):
        resp = self.app.post(
            reverse("ClusterUpgradeHandler",
                    kwargs={"cluster_id": 42}),
            jsonutils.dumps(self.data),
            headers=self.default_headers,
            expect_errors=True)
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json_body["message"], "Cluster not found")

    def test_clone_cluster_already_in_upgrade_error(self):
        self.app.post(
            reverse("ClusterUpgradeHandler",
                    kwargs={"cluster_id": self.cluster_61.id}),
            jsonutils.dumps(self.data),
            headers=self.default_headers)
        resp = self.app.post(
            reverse("ClusterUpgradeHandler",
                    kwargs={"cluster_id": self.cluster_61.id}),
            jsonutils.dumps(self.data),
            headers=self.default_headers,
            expect_errors=True)
        self.assertEqual(resp.status_code, 400)

    def test_clone_cluster_name_already_exists_error(self):
        data = dict(self.data, name=self.cluster_61.name)
        resp = self.app.post(
            reverse("ClusterUpgradeHandler",
                    kwargs={"cluster_id": self.cluster_61.id}),
            jsonutils.dumps(data),
            headers=self.default_headers,
            expect_errors=True)
        self.assertEqual(resp.status_code, 409)
