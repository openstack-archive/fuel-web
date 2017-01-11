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

import six

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as psql

from nailgun.api.v1.validators.base import BasicValidator
from nailgun.api.v1.validators.json_schema import release
from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun import errors


class ReleaseValidator(BasicValidator):

    @classmethod
    def _validate_common(cls, d, instance=None):
        if not instance:
            instance = {}
        if "networks_metadata" in d:
            # TODO(enchantner): additional validation
            meta = d["networks_metadata"]["nova_network"]
            for network in meta["networks"]:
                if "name" not in network:
                    raise errors.InvalidData(
                        "Invalid network data: {0}".format(network),
                        log_message=True
                    )
        if 'roles_metadata' in d:
            roles_meta = d['roles_metadata']
            tags_meta = d.get('tags_metadata',
                              instance.get('tags_metadata', {}))
            available_tags = set(tags_meta)
            for role_name, meta in six.iteritems(roles_meta):
                role_tags = set(meta.get('tags', []))
                missing_tags = role_tags - available_tags
                if missing_tags:
                    raise errors.InvalidData(
                        "Tags {} are present for role {}, but, absent in "
                        "release tags metadata".format(missing_tags,
                                                       role_name),
                        log_message=True
                    )

    @classmethod
    def validate(cls, data):
        d = cls.validate_json(data)
        if "name" not in d:
            raise errors.InvalidData(
                "No release name specified",
                log_message=True
            )
        if "version" not in d:
            raise errors.InvalidData(
                "No release version specified",
                log_message=True
            )
        if "operating_system" not in d:
            raise errors.InvalidData(
                "No release operating system specified",
                log_message=True
            )

        if db().query(models.Release).filter_by(
            name=d["name"],
            version=d["version"]
        ).first():
            raise errors.AlreadyExists(
                "Release with the same name and version "
                "already exists",
                log_message=True
            )

        cls._validate_common(d)

        if "networks_metadata" not in d:
            d["networks_metadata"] = {}
        if "attributes_metadata" not in d:
            d["attributes_metadata"] = {}

        return d

    @classmethod
    def validate_update(cls, data, instance):
        d = cls.validate_json(data)
        cls._validate_common(d, instance)

        if db().query(models.Release).filter_by(
            name=d.get("name", instance.name),
            version=d.get("version", instance.version)
        ).filter(
            sa.not_(models.Release.id == instance.id)
        ).first():
            raise errors.AlreadyExists(
                "Release with the same name "
                "and version already exists",
                log_message=True
            )

        if 'roles_metadata' in d:
            deleted_roles = (set(instance.roles_metadata) -
                             set(d['roles_metadata']))
            clusters_ids = (cluster.id for cluster in instance.clusters)

            deleted_roles_array = sa.cast(
                psql.array(deleted_roles),
                psql.ARRAY(sa.String(consts.ROLE_NAME_MAX_SIZE)))

            node = db().query(models.Node).filter(
                models.Node.cluster_id.in_(clusters_ids)
            ).filter(sa.or_(
                models.Node.roles.overlap(deleted_roles_array),
                models.Node.pending_roles.overlap(deleted_roles_array)
            )).first()

            if node:
                used_role = set(node.roles + node.pending_roles)
                used_role = used_role.intersection(deleted_roles)

                raise errors.CannotDelete(
                    "The following roles: {0} cannot be deleted "
                    "since they are already assigned "
                    "to nodes.".format(','.join(used_role))
                )

        return d

    @classmethod
    def validate_delete(cls, data, instance):
        if instance.clusters:
            raise errors.CannotDelete(
                "Can't delete release with "
                "clusters assigned"
            )


class ReleaseAttributesMetadataValidator(BasicValidator):

    single_schema = release.ATTRIBUTES_METADATA_SCHEMA


class ReleaseNetworksValidator(BasicValidator):

    @classmethod
    def validate(cls, data):
        parsed = super(ReleaseNetworksValidator, cls).validate(data)
        cls.validate_schema(parsed)
        return parsed

    @classmethod
    def validate_schema(cls, data):
        return super(ReleaseNetworksValidator, cls).validate_schema(
            data, release.NETWORKS_SCHEMA)
