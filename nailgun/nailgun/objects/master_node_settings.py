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

import six

from nailgun.db import db
from nailgun.db.sqlalchemy.models import MasterNodeSettings
from nailgun.errors import errors
from nailgun import logger
from nailgun.objects.base import NailgunObject
from nailgun.objects.serializers.master_node_settings \
    import MasterNodeSettingsSerializer


class MasterNodeSettings(NailgunObject):

    model = MasterNodeSettings

    serializer = MasterNodeSettingsSerializer

    schema = {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "title": "ActionLog",
        "description": "Serialized ActionLog object",
        "type": "object",
        "properties": {
            "settings": {"type": "object"}
        }
    }

    @classmethod
    def get_one(cls, fail_if_not_found=False, lock_for_update=False):
        """Get one instance from table.

        :param fail_if_not_found: raise an exception if object is not found
        :param lock_for_update: lock returned object for update (DB mutex)
        :return: instance of an object (model)
        """
        q = db().query(cls.model)
        if lock_for_update:
            q = q.with_lockmode('update')

        res = q.first()

        if not res and fail_if_not_found:
            raise errors.ObjectNotFound(
                "Object '{0}' is not found in DB".format(cls.__name__)
            )
        return res

    @classmethod
    def update(cls, instance, data):
        """Update MasterNodeSettings object instance with specified parameters
        in DB. master_node_uid cannot be changed so it's ignored.

        :param instance: MasterNodeSettings instance
        :param data: dictionary of key-value pairs as object fields
        :returns: MasterNodeSettings instance
        """
        # master_node_uid cannot be changed
        data.pop("master_node_uid", None)

        super(MasterNodeSettings, cls).update(instance, data)
        return instance

    @classmethod
    def must_send_stats(cls):
        try:
            stat_settings = getattr(
                cls.get_one(), "settings", {}
            ).get("statistics", {})
            return stat_settings.get("user_choice_saved", {}).\
                get("value", False) and \
                stat_settings.get("send_anonymous_statistic", {}). \
                get("value", False)
        except (AttributeError, TypeError) as e:
            logger.exception(
                "Get statistics settings failed: %s", six.text_type(e))
            return False
