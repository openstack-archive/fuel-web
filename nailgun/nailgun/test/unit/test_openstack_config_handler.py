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

import urllib

from oslo_serialization import jsonutils

from nailgun.db import db
from nailgun import objects
from nailgun.test.base import BaseIntegrationTest
from nailgun.utils import reverse


class TestOpenstackConfigHandlers(BaseIntegrationTest):

    def setUp(self):
        super(TestOpenstackConfigHandlers, self).setUp()

        self.cluster = self.env.create_cluster(api=False)
        self.nodes = self.env.create_nodes(3)
        self.create_openstack_config(cluster_id=self.cluster.id, config={})
        self.create_openstack_config(
            cluster_id=self.cluster.id, node_id=self.nodes[1].id, config={})

    def create_openstack_config(self, **kwargs):
        config = objects.OpenstackConfig.create(kwargs)
        db().commit()
        return config

    def test_openstack_config_upload(self):
        data = {
            'cluster_id': self.cluster.id,
            'node_id': self.nodes[0].id,
            'config': {}
        }

        resp = self.app.post(
            reverse('OpenstackConfigsHandler'),
            jsonutils.dumps(data),
            headers=self.default_headers)

        self.assertEqual(resp.status_code, 200)

    @classmethod
    def _make_filter_url(cls, **kwargs):
        return '{0}?{1}'.format(
            reverse('OpenstackConfigsHandler'),
            urllib.urlencode(kwargs))

    def test_openstack_config_list(self):
        url = self._make_filter_url(cluster_id=self.cluster.id)
        resp = self.app.get(url, headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json_body), 2)

        url = self._make_filter_url(
            cluster_id=self.cluster.id, node_id=self.nodes[1].id)
        resp = self.app.get(url, headers=self.default_headers)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json_body), 1)
