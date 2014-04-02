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

from mock import patch

from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import reverse


class TestPagination(BaseIntegrationTest):

    def test_node_pagination(self):
        for n in xrange(20):
            self.env.create_node(api=False)

        with patch(
            'nailgun.api.handlers.node.NodeCollectionHandler.default_limit',
            5
        ):
            resp = self.app.get(
                reverse('NodeCollectionHandler'),
                headers=self.default_headers
            )
            response = json.loads(resp.body)

            self.assertIn("objects", response)
            self.assertIn("meta", response)
            self.assertEquals(5, len(response["objects"]))
            self.assertEquals(response["meta"]["total_count"], 20)
            self.assertEquals(response["meta"]["limit"], 5)
            self.assertEquals(response["meta"]["offset"], 0)
            objects_ids = set((o["id"] for o in response["objects"]))

            resp = self.app.get(
                reverse('NodeCollectionHandler'),
                headers=self.default_headers
            )
            response = json.loads(resp.body)

            self.assertEqual(
                objects_ids,
                set((o["id"] for o in response["objects"]))
            )

            resp = self.app.get(
                reverse('NodeCollectionHandler') + "?offset=5",
                headers=self.default_headers
            )
            response = json.loads(resp.body)

            self.assertEquals(response["meta"]["offset"], 5)
            self.assertNotEqual(
                objects_ids,
                set((o["id"] for o in response["objects"]))
            )

        with patch(
            'nailgun.api.handlers.node.NodeCollectionHandler.default_limit',
            7
        ):
            resp = self.app.get(
                reverse('NodeCollectionHandler'),
                headers=self.default_headers
            )
            response = json.loads(resp.body)
            self.assertEquals(7, len(response["objects"]))

        resp = self.app.get(
            reverse('NodeCollectionHandler') + "?limit=8",
            headers=self.default_headers
        )
        response = json.loads(resp.body)
        self.assertEquals(8, len(response["objects"]))
