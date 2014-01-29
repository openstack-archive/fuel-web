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


from nailgun.db.sqlalchemy.models import Cluster
from nailgun.db.sqlalchemy.models import fencing
from nailgun.db.sqlalchemy.models import FencingConfiguration
from nailgun.db.sqlalchemy.models import FencingPrimitive
from nailgun.test.base import BaseIntegrationTest


class TestFencingDB(BaseIntegrationTest):

    def test_create_configuration(self):
        cl_descr = self.env.create(
            cluster_kwargs={
                "mode": "ha_compact"
            }
        )
        cluster = self.db.query(Cluster).get(cl_descr['id'])
        self.assertTrue(hasattr(cluster, 'fencing_config'))
        self.assertIsNone(cluster.fencing_config)

        self.db.add(
            FencingConfiguration(
                cluster_id=cl_descr['id'],
                policy=fencing.FENCING_POLICIES.disabled)
        )
        self.db.commit()
        cluster = self.db.query(Cluster).get(cl_descr['id'])
        self.assertIsNotNone(cluster.fencing_config)
        self.assertEqual(cluster.fencing_config.cluster_id, cluster.id)
        self.assertEqual(cluster.fencing_config.policy,
                         fencing.FENCING_POLICIES.disabled)

    def test_create_primitives(self):
        cl_descr = self.env.create(
            cluster_kwargs={
                "mode": "ha_compact"
            },
            nodes_kwargs=[
                {"pending_addition": True},
                {"pending_addition": True},
                {"pending_addition": True},
            ]
        )
        self.db.add(
            FencingConfiguration(
                cluster_id=cl_descr['id'],
                policy=fencing.FENCING_POLICIES.disabled)
        )
        self.db.commit()
        cluster = self.db.query(Cluster).get(cl_descr['id'])
        fence_cfg = cluster.fencing_config
        self.assertEqual(len(fence_cfg.primitives), 0)
        for n in cluster.nodes:
            self.db.add(
                FencingPrimitive(
                    name="ipmilan",
                    index=1,
                    configuration_id=fence_cfg.id,
                    node_id=n.id,
                    parameters={
                        "ipaddr": "199.11.111.1",
                        "login": "ipmilan",
                        "passwd": "ipmilan"
                    }
                ))
        fence_cfg.policy = fencing.FENCING_POLICIES.poweroff
        self.db.commit()
        self.db.refresh(fence_cfg)
        self.assertEqual(len(fence_cfg.primitives), 3)
