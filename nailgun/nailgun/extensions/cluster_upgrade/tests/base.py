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

from nailgun import consts
from nailgun.test import base as nailgun_test_base

from .. import upgrade
from ..objects import adapters


class BaseCloneClusterTest(nailgun_test_base.BaseIntegrationTest):
    helper = upgrade.UpgradeHelper

    def setUp(self):
        super(BaseCloneClusterTest, self).setUp()
        self.release_61 = self.env.create_release(
            operating_system=consts.RELEASE_OS.ubuntu,
            version="2014.2.2-6.1",
        )
        self.release_70 = self.env.create_release(
            operating_system=consts.RELEASE_OS.ubuntu,
            version="2015.1.0-7.0",
        )
        cluster = self.env.create_cluster(
            api=False,
            release_id=self.release_61.id,
            net_provider=consts.CLUSTER_NET_PROVIDERS.neutron,
            net_l23_provider=consts.NEUTRON_L23_PROVIDERS.ovs,
        )
        self.orig_cluster = adapters.NailgunClusterAdapter(cluster)
        self.data = {
            "name": "cluster-clone",
            "release_id": self.release_70.id,
        }
