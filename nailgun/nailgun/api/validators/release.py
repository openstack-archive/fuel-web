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

from sqlalchemy import not_

from nailgun.api.validators.base import BasicValidator
from nailgun.db import db
from nailgun.db.sqlalchemy.models import Release
from nailgun.errors import errors


class ReleaseValidator(BasicValidator):

    @classmethod
    def _validate_common(cls, d):
        if "networks_metadata" in d:
            # TODO(enchantner): additional validation
            meta = d["networks_metadata"]["nova_network"]
            for network in meta["networks"]:
                if "name" not in network:
                    raise errors.InvalidData(
                        "Invalid network data: {0}".format(network),
                        log_message=True
                    )
        if "orchestrator_data" in d:
            if not isinstance(d["orchestrator_data"], dict):
                raise errors.InvalidData(
                    "'orchestrator_data' field must be a dict",
                    log_message=True
                )
            keys = set(["repo_metadata",
                        "puppet_manifests_source",
                        "puppet_modules_source"])
            if not (set(d["orchestrator_data"].keys()) >= keys):
                raise errors.InvalidData(
                    "'orchestrator_data' doesn't have all required keys",
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
        if db().query(Release).filter_by(
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
        cls._validate_common(d)

        if db().query(Release).filter_by(
            name=d.get("name", instance.name),
            version=d.get("version", instance.version)
        ).filter(
            not_(Release.id == instance.id)
        ).first():
            raise errors.AlreadyExists(
                "Release with the same name "
                "and version already exists",
                log_message=True
            )

        if "roles" in d:
            new_roles = set(d["roles"])
            assigned_roles_names = set([
                r.name for r in instance.role_list
                if r.nodes or r.pending_nodes
            ])
            if not assigned_roles_names <= new_roles:
                raise errors.InvalidData(
                    "Cannot delete roles already "
                    "assigned to nodes: {0}".format(
                        ", ".join(assigned_roles_names - new_roles)
                    ),
                    log_message=True
                )
        return d

    @classmethod
    def validate_delete(cls, instance):
        if instance.clusters:
            raise errors.CannotDelete(
                "Can't delete release with "
                "clusters assigned"
            )
