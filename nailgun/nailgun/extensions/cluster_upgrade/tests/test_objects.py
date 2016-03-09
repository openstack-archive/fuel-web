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

from nailgun.extensions.cluster_upgrade import models
from nailgun.extensions.cluster_upgrade.objects import relations as objects


class TestUpgradeRelationObject(BaseIntegrationTest):
    def test_get_and_create_relation(self):
        objects.UpgradeRelationObject.create_relation(1, 2)
        rel0 = objects.UpgradeRelationObject.get_cluster_relation(1)
        self.assertEqual(rel0.orig_cluster_id, 1)
        self.assertEqual(rel0.seed_cluster_id, 2)
        rel1 = objects.UpgradeRelationObject.get_cluster_relation(2)
        self.assertEqual(rel1.orig_cluster_id, 1)
        self.assertEqual(rel1.seed_cluster_id, 2)

    def test_is_cluster_in_upgrade(self):
        objects.UpgradeRelationObject.create_relation(1, 2)
        in_upgrade = objects.UpgradeRelationObject.is_cluster_in_upgrade
        self.assertTrue(in_upgrade(1))
        self.assertTrue(in_upgrade(2))

    def test_is_cluster_not_in_upgrade(self):
        self.assertEqual(self.db.query(models.UpgradeRelation).count(), 0)
        in_upgrade = objects.UpgradeRelationObject.is_cluster_in_upgrade
        self.assertFalse(in_upgrade(1))
        self.assertFalse(in_upgrade(2))

    def test_delete_relation(self):
        objects.UpgradeRelationObject.create_relation(1, 2)
        objects.UpgradeRelationObject.delete_relation(1)
        self.assertEqual(self.db.query(models.UpgradeRelation).count(), 0)
