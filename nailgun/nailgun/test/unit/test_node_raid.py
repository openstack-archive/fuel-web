# -*- coding: utf-8 -*-

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

import json

from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import reverse


class TestRaidHandlers(BaseIntegrationTest):

    def test_get_handler(self):
        resp = self.app.get(reverse('NodeRaidHandler',
                                    kwargs={'node_id': 1}),
                            expect_errors=True,
                            headers=self.default_headers)
        self.assertEquals(resp.status_code, 200)


class TestDefaultsRaidHandlers(BaseIntegrationTest):

    def get(self, node_id):
        resp = self.app.get(reverse('NodeDefaultsRaidHandler',
                                    kwargs={'node_id': node_id}),
                            expect_errors=True,
                            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)
        return json.loads(resp.body)

    def test_get_handler(self):
        cluster = self.env.create_cluster(api=True)
        self.env.create_node(
            api=True,
            pending_roles=['controller'],
            cluster_id=cluster['id'])

        node_db = self.env.nodes[0]

        new_meta = node_db.meta.copy()

        raid_meta = {"controllers":
                     [{"product_name": "LSI MegaRAID SAS 9260-4i",
                       "controller_id": "0",
                       "vendor": "lsi"}]}
        raid_meta["controllers"][0]["physical_drives"] = [
            {"sector_size": "512B",
             "medium": "HDD",
             "enclosure": "252",
             "slot": "0",
             "model": "ST1000NM0011",
             "interface": "SATA"},
            {"sector_size": "512B",
             "medium": "HDD",
             "enclosure": "251",
             "slot": "1",
             "model": "ST1000NM0011",
             "interface": "SATA"},
        ]

        new_meta['raid'] = raid_meta

        self.app.put(
            reverse('NodeAgentHandler'),
            json.dumps({
                "mac": node_db.mac,
                "meta": new_meta}),
            headers=self.default_headers)

        self.env.refresh_nodes()

        response = self.get(node_db.id)
        self.assertTrue(len(response["raids"]) > 0)
