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
    def test_post(self):
        resp = self.app.post(
            reverse('ClusterUpgradeHandler',
                    kwargs={'cluster_id': self.orig_cluster.id}),
            jsonutils.dumps(self.data),
            headers=self.default_headers)
        body = resp.json_body
        self.assertEqual(200, resp.status_code)
        self.assertEqual("cluster-clone", body["name"])
        self.assertEqual(self.release_70.id, body["release_id"])
