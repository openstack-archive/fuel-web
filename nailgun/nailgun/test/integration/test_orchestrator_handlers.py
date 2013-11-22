# -*- coding: utf-8 -*-

#    Copyright 2013 Mirantis, Inc.
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

import json

from nailgun.db.sqlalchemy.models import Cluster
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import reverse


class TestHandlers(BaseIntegrationTest):

    def setUp(self):
        super(TestHandlers, self).setUp()
        self.cluster = self.env.create_cluster(api=False)

    def check_info_handler(self, handler_name, get_info):
        # updating provisioning info
        orchestrator_data = {"field": "test"}
        put_resp = self.app.put(
            reverse(handler_name,
                    kwargs={'cluster_id': self.cluster.id}),
            json.dumps(orchestrator_data),
            headers=self.default_headers)

        self.assertEquals(put_resp.status, 200)
        self.assertEquals(get_info(), orchestrator_data)

        # getting provisioning info
        get_resp = self.app.get(
            reverse(handler_name,
                    kwargs={'cluster_id': self.cluster.id}),
            headers=self.default_headers)

        self.assertEquals(get_resp.status, 200)
        self.datadiff(orchestrator_data, json.loads(get_resp.body))

        # deleting provisioning info
        delete_resp = self.app.delete(
            reverse(handler_name,
                    kwargs={'cluster_id': self.cluster.id}),
            headers=self.default_headers)

        self.assertEquals(delete_resp.status, 202)
        self.assertEqual(get_info(), {})

    def test_cluster_provisioning_info(self):
        self.check_info_handler(
            'ProvisioningInfo',
            lambda: self.cluster.replaced_provisioning_info)

    def test_cluster_deployment_info(self):
        self.check_info_handler(
            'DeploymentInfo',
            lambda: self.cluster.replaced_deployment_info)


class TestDefaultOrchestratorHandlers(BaseIntegrationTest):

    def setUp(self):
        super(TestDefaultOrchestratorHandlers, self).setUp()

        cluster = self.env.create(
            cluster_kwargs={
                'mode': 'multinode'},
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True},
                {'roles': ['compute'], 'pending_addition': True},
                {'roles': ['cinder'], 'pending_addition': True}])

        self.cluster = self.db.query(Cluster).get(cluster['id'])

    def customization_handler_helper(self, handler_name, get_info):
        facts = {"key": "value"}
        resp = self.app.put(
            reverse(handler_name,
                    kwargs={'cluster_id': self.cluster.id}),
            json.dumps(facts),
            headers=self.default_headers)
        self.assertEqual(resp.status, 200)
        self.assertTrue(self.cluster.is_customized)
        self.datadiff(get_info(), facts)

    def test_default_deployment_handler(self):
        resp = self.app.get(
            reverse('DefaultDeploymentInfo',
                    kwargs={'cluster_id': self.cluster.id}),
            headers=self.default_headers)

        self.assertEqual(resp.status, 200)
        self.assertEqual(3, len(json.loads(resp.body)))

    def test_default_provisioning_handler(self):
        resp = self.app.get(
            reverse('DefaultProvisioningInfo',
                    kwargs={'cluster_id': self.cluster.id}),
            headers=self.default_headers)

        self.assertEqual(resp.status, 200)
        self.assertEqual(3, len(json.loads(resp.body)['nodes']))

    def test_cluster_provisioning_customization(self):
        self.customization_handler_helper(
            'ProvisioningInfo',
            lambda: self.cluster.replaced_provisioning_info
        )

    def test_cluster_deployment_customization(self):
        self.customization_handler_helper(
            'DeploymentInfo',
            lambda: self.cluster.replaced_deployment_info
        )
