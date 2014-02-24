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

from nailgun.db.sqlalchemy.models import network
from nailgun.settings import settings
from nailgun.test import base


class TestDefaultIpAddr(base.BaseTestCase):

    def test_default_ip_addr_with_admin_network(self):
        ips = self.db.query(network.IPAddr).all()
        self.assertEqual(len(ips), 1)
        self.assertEqual(ips[0].ip_addr, settings.MASTER_IP)
        network_group = ips[0].network_data
        self.assertEqual(network_group.name, 'fuelweb_admin')
