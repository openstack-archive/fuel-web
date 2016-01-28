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

from nailgun.api.v1.validators.base import BasicValidator
from nailgun.api.v1.validators.json_schema import plugin_link
from nailgun.db import db
from nailgun.errors import errors


class PluginLinkValidator(BasicValidator):
    collection_schema = plugin_link.PLUGIN_LINKS_SCHEMA

    @classmethod
    def _check_url_uniquenes(cls, data, model):
        query = db().query(model).filter_by(
            url=data["url"]
        )
        if db().query(query.exists()).scalar():
            raise errors.AlreadyExists(
                "Link with the same url {0} "
                "already exists".format(data["url"]),
                log_message=True
            )

    @classmethod
    def validate(cls, data, model):
        parsed = super(PluginLinkValidator, cls).validate(data)
        cls.validate_schema(
            parsed,
            plugin_link.PLUGIN_LINK_SCHEMA
        )
        cls._check_url_uniquenes(parsed, model)
        return parsed

    @classmethod
    def validate_update(cls, data, instance, model):
        parsed = super(PluginLinkValidator, cls).validate(data)
        cls.validate_schema(
            parsed,
            plugin_link.PLUGIN_LINK_UPDATE_SCHEMA
        )
        new_url = parsed.get("url")
        if new_url and new_url != instance.url:
            cls._check_url_uniquenes(parsed, model)
        return parsed
