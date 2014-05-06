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

from nailgun.raid.manager import RaidManager
from nailgun.raid.manager import RaidType
from nailgun.test.base import BaseTestCase


class TestRaidManagerDefaultConfiguration(BaseTestCase):

    def setUp(self):
        super(TestRaidManagerDefaultConfiguration, self).setUp()
        self.env.create(
            nodes_kwargs=[{'pending_roles': ['controller']}])
        self.env.create_node()

    def test_default_config_empty(self):
        raid_conf = RaidManager.get_default_raid_configuration(
            self.env.nodes[0])

        self.assertEqual(raid_conf, {})

    def test_default_config_single_disk(self):
        """Tests configuration when we only have one
        disk available. The expected result would be a jbod
        for the root partition.
        """
        node = self.env.nodes[0]
        node.meta["raid"] = {"controllers":
                             [{"product_name": "LSI MegaRAID SAS 9260-4i",
                               "controller_id": "0",
                               "vendor": "lsi"}]}
        node.meta["raid"]["controllers"][0]["physical_drives"] = [
            {"sector_size": "512B",
             "medium": "HDD",
             "enclosure": "252",
             "slot": "0",
             "model": "ST1000NM0011",
             "interface": "SATA"}]

        raid_conf = RaidManager.get_default_raid_configuration(
            node)
        configured_raids = raid_conf["raids"]
        self.assertEqual(len(configured_raids), 1)
        self.assertEqual(configured_raids[0]["mount_point"], "/")
        self.assertEqual(configured_raids[0]["raid_lvl"], "jbod")
        self.assertEqual(configured_raids[0]["ctrl_id"], "0")
        self.assertEqual(configured_raids[0]["phys_devices"], ["0"])

    def test_default_config_two_disks(self):
        """Tests configuration with two disks available, the
        expected result would be RAID1 configured for the root
        partition.
        """
        node = self.env.nodes[0]
        node.meta["raid"] = {"controllers":
                             [{"product_name": "LSI MegaRAID SAS 9260-4i",
                               "controller_id": "0",
                               "vendor": "lsi"}]}
        node.meta["raid"]["controllers"][0]["physical_drives"] = [
            {"sector_size": "512B",
             "medium": "HDD",
             "enclosure": "252",
             "slot": "0",
             "model": "ST1000NM0011",
             "interface": "SATA"},
            {"sector_size": "512B",
             "medium": "HDD",
             "enclosure": "252",
             "slot": "1",
             "model": "ST1000NM0011",
             "interface": "SATA"}]

        raid_conf = RaidManager.get_default_raid_configuration(
            node)
        configured_raids = raid_conf["raids"]
        self.assertEqual(len(configured_raids), 1)
        self.assertEqual(configured_raids[0]["mount_point"], "/")
        self.assertEqual(configured_raids[0]["raid_lvl"], RaidType.RAID1)
        self.assertEqual(set(configured_raids[0]["phys_devices"]),
                         set(["0", "1"]))
        self.assertEqual(configured_raids[0]["ctrl_id"], "0")
