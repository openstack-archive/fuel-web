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

from nailgun.db.sqlalchemy import models

from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject

from nailgun.objects.serializers.action_log import ActionLogSerializer


class ActionLog(NailgunObject):

    #: SQLAlchemy model for ActionLog
    model = models.ActionLogs

    #: Serializer for ActionLog
    serializer = ActionLogSerializer

    #: JSON schema for ActionLog
    schema = {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "title": "ActionLog",
        "description": "Serialized ActionLog object",
        "type": "object",
        "properties": {
            "id": {"type": "number"},
            "actor_id": {"type": "string"},
            "action_group": {"type": "string"},
            "action_name": {"type": "string"},
            "request_data": {
                "type": "object",
                "data": {"type": ["object", "null"]},
                "url": {"type": "string"},
                "message": {"type": ["string", "null"]},
                "http_method": {"type": "string"}
            },
            "response_data": {
                "type": "object",
                "data": {"type": ["object", "null"]},
                "status": {"type": "string"},
                "message": {"type": ["string", "null"]}
            },
            "start_timestamp": {"type": "string"},
            "end_timestamp": {"type": "string"},

            "is_sent": {"type": "boolean"}
        }
    }


class ActionLogCollection(NailgunCollection):
    single = ActionLog
