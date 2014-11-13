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

from nailgun import objects

from nailgun.db.sqlalchemy.models import IPAddr
from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks


class TestHorizonURL(BaseIntegrationTest):

    def tearDown(self):
        self._wait_for_threads()
        super(TestHorizonURL, self).tearDown()

    @fake_tasks(godmode=True)
    def test_horizon_url_ha_mode(self):
        self.env.create(
            nodes_kwargs=[
                {"pending_addition": True},
                {"pending_addition": True},
                {"pending_addition": True},
            ]
        )

        supertask = self.env.launch_deployment()
        self.env.wait_ready(supertask, 60)

        network = self.db.query(NetworkGroup).\
            filter(NetworkGroup.group_id ==
                   objects.Cluster.get_default_group(
                       self.env.clusters[0]).id).\
            filter_by(name="public").first()
        lost_ips = self.db.query(IPAddr).filter_by(
            network=network.id,
            node=None
        ).all()
        self.assertEqual(len(lost_ips), 1)

        self.assertEqual(supertask.message, (
            u"Deployment of environment '{0}' is done. "
            "Access the OpenStack dashboard (Horizon) at http://{1}/"
        ).format(
            self.env.clusters[0].name,
            lost_ips[0].ip_addr
        ))
