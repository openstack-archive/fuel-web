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


from nailgun.objects.base import NailgunObject
from nailgun.objects.serializers.master_node_settings \
    import MasterNodeSettingsSerializer

from nailgun.db import db
from nailgun.db.sqlalchemy.models import MasterNodeSettings

from nailgun.errors import errors


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
