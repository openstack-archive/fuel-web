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

from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun.network import manager
from nailgun.test import base


class TestReusingAdminAddress(base.BaseTestCase):

    def setUp(self):
        super(TestReusingAdminAddress, self).setUp()
        self.reuse_nodes = []
        self.reuse_nodes.append(self.env.create_node(ip='10.10.0.3'))
        self.reuse_nodes.append(self.env.create_node(ip='10.10.0.4'))
        self.assign_from_new = self.env.create_node(ip='10.10.0.12')
        # flush ranges from admin group
        self.admin_ng = db().query(models.NetworkGroup).filter_by(
            name="fuelweb_admin").first()
        self.admin_ng.ip_ranges.remove(self.admin_ng.ip_ranges[0])
        db().flush()

    def test_verifies_that_node_will_reuse_its_ip_address(self):
        ip_range = models.IPAddrRange(
            first='10.10.0.3',
            last='10.10.0.9')
        self.admin_ng.ip_ranges.append(ip_range)
        db().flush()
        manager.NetworkManager.assign_admin_ips(self.env.nodes)
        for node in self.reuse_nodes:
            self.assertEqual(len(node.ip_addrs), 1)
            ip = node.ip_addrs[0]
            self.assertEqual(node.ip, ip.ip_addr)
        self.assertEqual(len(self.assign_from_new.ip_addrs), 1)
        ip = self.assign_from_new.ip_addrs[0]
        self.assertEqual(ip.ip_addr, '10.10.0.5')
