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

import sqlalchemy as sa

from nailgun.api.v1.validators.base import BasicValidator
from nailgun.api.v1.validators.json_schema import role
from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun import errors


class RoleValidator(BasicValidator):

    @classmethod
    def validate_delete(cls, release, role_name):
        clusters = [cluster.id for cluster in release.clusters]
        node = db().query(models.Node).filter(
            models.Node.cluster_id.in_(clusters)
        ).filter(sa.or_(
            models.Node.roles.any(role_name),
            models.Node.pending_roles.any(role_name)
        )).first()

        if node:
            raise errors.CannotDelete(
                "Can't delete roles that is assigned to some node.")

    @classmethod
    def validate(cls, data, instance=None):
        parsed = super(RoleValidator, cls).validate(data)
        cls.validate_schema(parsed, role.SCHEMA)
        return parsed

    @classmethod
    def validate_update(cls, data, instance):
        parsed = cls.validate(data, instance=instance)

        allowed_ids = [m['id'] for m in instance.volumes_metadata['volumes']]
        missing_volume_ids = []
        for volume in parsed['volumes_roles_mapping']:
            if volume['id'] not in allowed_ids:
                missing_volume_ids.append(volume['id'])

        if missing_volume_ids:
            raise errors.InvalidData(
                "Wrong data in volumes_roles_mapping. Volumes with ids {0} are"
                " not in the list of allowed volumes {1}".format(
                    missing_volume_ids, allowed_ids))

        return parsed

    @classmethod
    def validate_create(cls, data):
        return cls.validate(data)
