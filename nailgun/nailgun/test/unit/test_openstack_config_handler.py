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
import urllib

from oslo_serialization import jsonutils

from nailgun.db import db
from nailgun import objects
from nailgun.objects.serializers.openstack_config import \
    OpenstackConfigSerializer
from nailgun.test.base import BaseIntegrationTest
from nailgun.utils import reverse


class TestOpenstackConfigHandlers(BaseIntegrationTest):

    def setUp(self):
        super(TestOpenstackConfigHandlers, self).setUp()

        self.env.create_cluster(api=False)
        self.env.create_cluster(api=False)

        self.clusters = self.env.clusters
        self.nodes = self.env.create_nodes(3)

        self.configs = []
        self.create_openstack_config(
            cluster_id=self.clusters[0].id, configuration={})
        self.create_openstack_config(
            cluster_id=self.clusters[0].id, node_id=self.nodes[1].id,
            is_active=False, configuration={
                'key_2': 'value_2_1'
            })
        self.create_openstack_config(
            cluster_id=self.clusters[0].id, node_id=self.nodes[1].id,
            configuration={
                'key_1': 'value_1_1'
            })

    def create_openstack_config(self, **kwargs):
        config = objects.OpenstackConfig.create(kwargs)
        db().commit()
        self.configs.append(config)
        return config

    def test_openstack_config_upload_new(self):
        data = {
            'cluster_id': self.clusters[0].id,
            'node_id': self.nodes[0].id,
            'configuration': {}
        }

        resp = self.app.post(
            reverse('OpenstackConfigCollectionHandler'),
            jsonutils.dumps(data),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 201)
        resp_data = resp.json_body
        self.assertEqual(resp_data['cluster_id'], self.clusters[0].id)
        self.assertEqual(resp_data['node_id'], self.nodes[0].id)

    def test_openstack_config_upload_override(self):
        data = {
            'cluster_id': self.clusters[0].id,
            'node_id': self.nodes[1].id,
            'configuration': {
                'key_1': 'value_1_2'
            }
        }
        resp = self.app.post(
            reverse('OpenstackConfigCollectionHandler'),
            jsonutils.dumps(data),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 201)
        resp_data = resp.json_body
        self.assertEqual(resp_data['cluster_id'], self.clusters[0].id)
        self.assertEqual(resp_data['node_id'], self.nodes[1].id)

        resp = self.app.get(
            reverse('OpenstackConfigHandler',
                    {'obj_id': self.configs[1].id}),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json_body['is_active'], False)

    def test_openstack_config_list(self):
        url = self._make_filter_url(cluster_id=self.clusters[0].id)
        resp = self.app.get(url, headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json_body), 2)

        url = self._make_filter_url(
            cluster_id=self.clusters[0].id, node_id=self.nodes[1].id)
        resp = self.app.get(url, headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json_body), 1)

        url = self._make_filter_url(
            cluster_id=self.clusters[0].id, is_active=0)
        resp = self.app.get(url, headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json_body), 1)
        self.assertFalse(resp.json_body[0]['is_active'])

        url = self._make_filter_url(cluster_id=self.clusters[1].id)
        resp = self.app.get(url, headers=self.default_headers)
        self.assertEqual(len(resp.json_body), 0)

    def test_openstack_config_list_fail(self):
        url = self._make_filter_url(
            cluster_id=self.clusters[0].id, node_id=self.nodes[0].id,
            node_role='controller')
        resp = self.app.get(url, headers=self.default_headers,
                            expect_errors=True)
        self.assertEqual(resp.status_code, 400)
        self.assertRegexpMatches(
            resp.json_body['message'],
            r"Parameter '\w+' conflicts with '\w+(, \w+)*'")

    def test_openstack_config_get(self):
        resp = self.app.get(
            reverse('OpenstackConfigHandler',
                    {'obj_id': self.configs[0].id}),
            headers=self.default_headers)

        self.assertEqual(resp.status_code, 200)
        config = resp.json_body
        self.assertDictContainsSubset({
            'cluster_id': self.configs[0].cluster_id,
            'node_id': self.configs[0].node_id,
            'node_role': self.configs[0].node_role,
        }, config)
        self.assertEqual(sorted(config.keys()),
                         sorted(OpenstackConfigSerializer.fields))

    def test_openstack_config_put(self):
        resp = self.app.put(
            reverse('OpenstackConfigHandler',
                    {'obj_id': self.configs[0].id}),
            expect_errors=True)
        self.assertEqual(resp.status_code, 405)

    @mock.patch('nailgun.task.task.rpc.cast')
    def test_openstack_config_execute(self, _):
        data = {'cluster_id': self.clusters[0].id}
        resp = self.app.put(
            reverse('OpenstackConfigExecuteHandler'),
            jsonutils.dumps(data), headers=self.default_headers
        )

        self.assertEqual(resp.status_code, 202)

    def test_openstack_config_delete(self):
        obj_id = self.configs[0].id

        resp = self.app.delete(
            reverse('OpenstackConfigHandler',
                    {'obj_id': obj_id}),
            expect_errors=True)
        self.assertEqual(resp.status_code, 204)

        resp = self.app.get(
            reverse('OpenstackConfigHandler',
                    {'obj_id': obj_id}),
            headers=self.default_headers)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json_body['is_active'], False)

        # Try delete already deleted object
        resp = self.app.delete(
            reverse('OpenstackConfigHandler',
                    {'obj_id': obj_id}),
            headers=self.default_headers, expect_errors=True)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.json_body['message'],
            "Configuration '{0}' has been already disabled.".format(obj_id))

    @classmethod
    def _make_filter_url(cls, **kwargs):
        return '{0}?{1}'.format(
            reverse('OpenstackConfigCollectionHandler'),
            urllib.urlencode(kwargs))
