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

from nailgun.db import db

from nailgun.extensions.cluster_upgrade import models


class UpgradeRelationObject(object):
    @staticmethod
    def _query_cluster_relations(cluster_id):
        return db.query(models.UpgradeRelation).filter(
            (models.UpgradeRelation.orig_cluster_id == cluster_id) |
            (models.UpgradeRelation.seed_cluster_id == cluster_id))

    @classmethod
    def get_cluster_relation(cls, cluster_id):
        return cls._query_cluster_relations(cluster_id).first()

    @classmethod
    def delete_relation(cls, cluster_id):
        cls._query_cluster_relations(cluster_id).delete()

    @classmethod
    def is_cluster_in_upgrade(cls, cluster_id):
        query = cls._query_cluster_relations(cluster_id).exists()
        return db.query(query).scalar()

    @classmethod
    def create_relation(cls, orig_cluster_id, seed_cluster_id):
        relation = models.UpgradeRelation(
            orig_cluster_id=orig_cluster_id,
            seed_cluster_id=seed_cluster_id)
        db.add(relation)
        db.flush()
