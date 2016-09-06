# -*- coding: utf-8 -*-

#    Copyright 2016 Mirantis, Inc.
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

"""
Tag object and collection
"""

from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject
from nailgun.objects.serializers.tag import TagSerializer


class Tag(NailgunObject):

    model = models.Tag
    serializer = TagSerializer

    @classmethod
    def get_by_release_or_cluster(cls, name, cluster):
        tag = db().query(models.Tag).filter(
            ((models.Tag.owner_id == cluster.release.id) &
             (models.Tag.owner_type == 'release')) |
            ((models.Tag.owner_id == cluster.id) &
             (models.Tag.owner_type == 'cluster')),
            models.Tag.tag == name
        ).first()

        return tag


class TagCollection(NailgunCollection):

    @classmethod
    def get_has_primary_tags(cls):
        return db().query(models.Tag).filter_by(has_primary=True)

    single = Tag
