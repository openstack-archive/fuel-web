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

from nailgun.test.base import BaseIntegrationTest
from nailgun.utils import reverse


class ClusterCloneIPsHandler(BaseIntegrationTest):

    def test_cluster_clone_ips_handler(self):
        orig_cluster = self.env.create(api=False)
        seed_cluster = self.env.create(
            api=False,
            nodes_kwargs=[{'role': 'controller'}])

        from ..objects import relations
        relations.UpgradeRelationObject.create_relation(orig_cluster['id'],
                                                        seed_cluster['id'])

        resp = self.app.post(
            reverse('ClusterCloneIPsHandler',
                    kwargs={'cluster_id': orig_cluster['id']}),
            headers=self.default_headers)
        self.assertEqual(200, resp.status_code)

    def test_cluster_clone_ips_handler_no_relation(self):
        orig_cluster = self.env.create(api=False)

        resp = self.app.post(
            reverse('ClusterCloneIPsHandler',
                    kwargs={'cluster_id': orig_cluster['id']}),
            headers=self.default_headers,
            expect_errors=True)
        self.assertEqual(400, resp.status_code)
        self.assertEqual("Cluster with ID {0} is not in upgrade stage."
                         .format(orig_cluster['id']),
                         resp.json_body['message'])

    def test_cluster_clone_ips_handler_wrong_cluster_id(self):
        orig_cluster = self.env.create(api=False)
        seed_cluster = self.env.create(
            api=False,
            nodes_kwargs=[{'role': 'controller'}])

        from ..objects import relations
        relations.UpgradeRelationObject.create_relation(orig_cluster['id'],
                                                        seed_cluster['id'])

        resp = self.app.post(
            reverse('ClusterCloneIPsHandler',
                    kwargs={'cluster_id': seed_cluster['id']}),
            headers=self.default_headers,
            expect_errors=True)
        self.assertEqual(400, resp.status_code)
        self.assertEqual("There is no original cluster with ID {0}."
                         .format(seed_cluster['id']),
                         resp.json_body['message'])

    def test_cluster_clone_ips_handler_wrong_controllers_amount(self):
        orig_cluster = self.env.create(api=False)
        seed_cluster = self.env.create(api=False)

        from ..objects import relations
        relations.UpgradeRelationObject.create_relation(orig_cluster['id'],
                                                        seed_cluster['id'])

        resp = self.app.post(
            reverse('ClusterCloneIPsHandler',
                    kwargs={'cluster_id': orig_cluster['id']}),
            headers=self.default_headers,
            expect_errors=True)
        self.assertEqual(400, resp.status_code)
        self.assertEqual("Seed cluster should has at least one controller",
                         resp.json_body['message'])
