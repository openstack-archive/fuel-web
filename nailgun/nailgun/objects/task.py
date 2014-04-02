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


from nailgun.api.serializers.task import TaskSerializer

from nailgun.db import db
from nailgun.db.sqlalchemy import models

from nailgun import consts

from nailgun.errors import errors
from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject


class Task(NailgunObject):

    model = models.Task
    serializer = TaskSerializer

    schema = {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "title": "Task",
        "description": "Serialized Task object",
        "type": "object",
        "properties": {
            "id": {"type": "number"},
            "cluster_id": {"type": "number"},
            "parent_id": {"type": "number"},
            "name": {
                "type": "string",
                "enum": list(consts.TASK_NAMES)
            },
            "message": {"type": "string"},
            "status": {
                "type": "string",
                "enum": list(consts.TASK_STATUSES)
            },
            "progress": {"type": "number"},
            "weight": {"type": "number"},
            "cache": {"type": "object"},
            "result": {"type": "object"}
        }
    }

    @classmethod
    def create_subtask(cls, instance, name):
        if name not in consts.TASK_NAMES:
            raise errors.InvalidData(
                "Invalid subtask name"
            )

        return cls.create({
            "name": name,
            "cluster_id": instance.cluster_id,
            "parent_id": instance.id
        })

    @classmethod
    def get_by_uuid(cls, uuid):
        # maybe consider using uuid as pk?
        return db().query(cls.model).filter_by(uuid=uuid).first()


class TaskCollection(NailgunCollection):

    single = Task

    @classmethod
    def get_by_cluster_id(cls, cluster_id):
        if cluster_id == '':
            return cls.filter_by(None, cluster_id=None)
        return cls.filter_by(None, cluster_id=cluster_id)
