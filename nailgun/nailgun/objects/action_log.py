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

from nailgun.db import db
from nailgun.db.sqlalchemy import models

from nailgun import consts

from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject

from nailgun.objects.serializers.action_log import ActionLogSerializer


class ActionLog(NailgunObject):

    #: SQLAlchemy model for ActionLog
    model = models.ActionLog

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
            "actor_id": {"type": ["string", "null"]},
            "action_group": {"type": "string"},
            "action_name": {"type": "string"},
            "action_type": {
                "type": "string",
                "enum": list(consts.ACTION_TYPES)
            },
            "start_timestamp": {"type": "string"},
            "end_timestamp": {"type": "string"},
            "additional_info": {"type": "object"},
            "is_sent": {"type": "boolean"},
            "cluster_id": {"type": ["number", "null"]},
            "task_uuid": {"type": ["string", "null"]}
        }
    }

    @classmethod
    def update(cls, instance, data):
        """Form additional info for further instance update.

        Extend corresponding method of the parent class.

        Side effects:
        overrides already present keys of additional_info attribute
        of instance if this attribute is present in data argument

        Arguments:
        instance - instance of ActionLog class that is processed
        data - dictionary containing keyword arguments for entity to be
        updated

        return - returned by parent class method value
        """

        if data.get('additional_info'):
            add_info = dict(instance.additional_info)
            add_info.update(data['additional_info'])
            data['additional_info'] = add_info

        return super(ActionLog, cls).update(instance, data)

    @classmethod
    def get_by_task_uuid(cls, task_uuid):
        """Get action_log entry by task_uuid.

        Arguments:
        task_uuid - uuid of task, using which row is retrieved

        return - matching instance of action_log entity
        """
        instance = db().query(models.ActionLog)\
            .filter_by(task_uuid=task_uuid)\
            .first()

        return instance


class ActionLogCollection(NailgunCollection):
    single = ActionLog
