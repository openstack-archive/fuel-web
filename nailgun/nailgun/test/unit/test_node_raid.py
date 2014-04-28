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

from nailgun.db.sqlalchemy.models import Task

from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks
from nailgun.test.base import reverse


class TestRaidHandlers(BaseIntegrationTest):

    def get(self, node_id):
        resp = self.app.get(
            reverse('NodeRaidHandler', kwargs={'node_id': node_id}),
            headers=self.default_headers)

        self.assertEquals(200, resp.status_code)
        return json.loads(resp.body)

    def put(self, node_id, data, expect_errors=False):
        resp = self.app.put(
            reverse('NodeRaidHandler', kwargs={'node_id': node_id}),
            json.dumps(data),
            headers=self.default_headers,
            expect_errors=expect_errors)

        if not expect_errors:
            self.assertEquals(200, resp.status_code)
            return json.loads(resp.body)
        else:
            return resp

    def test_get_handler_with_wrong_nodeid(self):
        resp = self.app.get(
            reverse('NodeRaidHandler', kwargs={'node_id': 1}),
            expect_errors=True,
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 404)

    def test_get_handler(self):
        node = self.env.create_node(api=True)

        resp = self.get(node["id"])

        self.assertEqual(resp, {})

    def test_put_handler(self):
        raid_config = {"raids": {"controllers": [{"name": "test"}]}}
        node_db = self.env.create_node()

        self.put(node_db.id, raid_config)

        resp = self.get(node_db.id)
        self.assertEqual(resp["raids"]["controllers"][0]["name"],
                         "test")


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


class TestNodeApplyHandler(BaseIntegrationTest):

    def _create_raid_config(self, node):
        raid_config = {"raids": [{"ctrl_id": "0",
                                 "mount_point": "/",
                                 "phys_devices": [],
                                 "eid": "252",
                                 "raid_lvl": 1}]}
        self.env.create(
            nodes_kwargs=[
                {"status": "ready",
                 "online": True}])

        self.app.put(
            reverse('NodeRaidHandler',
                    kwargs={'node_id': node.id}),
            json.dumps(raid_config),
            headers=self.default_headers)

    def test_success_get_handler(self):
        self.env.create(
            nodes_kwargs=[
                {"status": "ready",
                 "online": True}])

        self._create_raid_config(self.env.nodes[0])

        resp = self.app.get(reverse('NodeRaidApplyHandler',
                                    kwargs={'node_id': self.env.nodes[0].id}),
                            expect_errors=True,
                            headers=self.default_headers)
        task = json.loads(resp.body)
        self.assertEqual(len(task["args"]["cmds"]), 2)
        self.assertEqual(task["args"]["cmds"][0]["action"], "clear_all")
        self.assertEqual(task["args"]["cmds"][1]["action"], "create")
        self.assertEqual(resp.status_code, 200)

    @fake_tasks()
    def test_success_put_handler(self):
        self.env.create(
            nodes_kwargs=[
                {'status': 'ready',
                 'online': True}])

        self._create_raid_config(self.env.nodes[0])

        resp = self.app.put(reverse('NodeRaidApplyHandler',
                                    kwargs={'node_id': self.env.nodes[0].id}),
                            expect_errors=True,
                            headers=self.default_headers)
        self.assertEquals(resp.status_code, 202)
        task = self.db.query(Task).filter(
            Task.name == 'raid',
            Task.node_id == self.env.nodes[0].id).first()
        self.assertIn(task.status, ('running', 'ready'))
        data = json.loads(resp.body)
        self.assertEquals(data['uuid'], task.uuid)

    @fake_tasks()
    def test_put_handler_without_existing_node(self):
        resp = self.app.put(reverse('NodeRaidApplyHandler',
                                    kwargs={'node_id': 1}),
                            expect_errors=True,
                            headers=self.default_headers)
        self.assertEquals(resp.status_code, 404)

    @fake_tasks()
    def test_put_handler_with_existing_node(self):
        self.env.create(
            nodes_kwargs=[
                {'status': 'ready',
                 'online': True}])

        self._create_raid_config(self.env.nodes[0])

        self.env.create_task(
            name='raid',
            node_id=self.env.nodes[0].id,
            status='running'
        )

        resp = self.app.put(reverse('NodeRaidApplyHandler',
                                    kwargs={'node_id': self.env.nodes[0].id}),
                            expect_errors=True,
                            headers=self.default_headers)
        tasks = self.db.query(Task).filter(
            Task.name == 'raid',
            Task.node_id == self.env.nodes[0].id).all()

        self.assertEquals(resp.status_code, 400)
        self.assertEquals(len(tasks), 1)

    @fake_tasks()
    def test_put_handler_without_raid_config(self):
        self.env.create(
            nodes_kwargs=[
                {'status': 'ready',
                 'online': True}])
        resp = self.app.put(reverse('NodeRaidApplyHandler',
                                    kwargs={'node_id': self.env.nodes[0].id}),
                            expect_errors=True,
                            headers=self.default_headers)
        tasks = self.db.query(Task).filter(
            Task.name == 'raid',
            Task.node_id == self.env.nodes[0].id).all()
        self.assertEquals(resp.status_code, 400)
        self.assertEquals(len(tasks), 1)
        self.assertEquals(tasks[0].status, 'error')
