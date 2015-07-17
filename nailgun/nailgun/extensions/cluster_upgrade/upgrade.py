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

from . import models


def _query_cluster_relations(cluster):
    return db.query(models.UpgradeRelation).filter(
        (models.UpgradeRelation.orig_cluster_id == cluster.id) |
        (models.UpgradeRelation.seed_cluster_id == cluster.id))


def delete_clusters_upgrade_relation(cluster):
    _query_cluster_relations(cluster).delete()


def is_cluster_in_upgrade(cluster):
    relation = _query_cluster_relations(cluster).first()
    return bool(relation)


def create_clusters_upgrade_relation(orig_cluster, seed_cluster):
    relation = models.UpgradeRelation(
        orig_cluster_id=orig_cluster.id,
        seed_cluster_id=seed_cluster.id)
    db.add(relation)
    db.flush()
