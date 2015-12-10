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

from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject

from nailgun.objects.serializers.action_log import ActionLogSerializer


class ActionLog(NailgunObject):

    #: SQLAlchemy model for ActionLog
    model = models.ActionLog

    #: Serializer for ActionLog
    serializer = ActionLogSerializer

    @classmethod
    def update(cls, instance, data):
        """Form additional info for further instance update.

        Extend corresponding method of the parent class.

        Side effects:
        overrides already present keys of additional_info attribute
        of instance if this attribute is present in data argument

        :param instance: instance of ActionLog class that is processed
        :param data: dictionary containing keyword arguments for entity to be
        updated

        :return: returned by parent class method value
        """
        instance.additional_info.update(data.pop('additional_info', {}))
        return super(ActionLog, cls).update(instance, data)

    @classmethod
    def get_by_kwargs(cls, **kwargs):
        """Get action_log entry by set of attributes values.

        :return: - matching instance of action_log entity
        """
        instance = db().query(models.ActionLog)\
            .filter_by(**kwargs)\
            .first()

        return instance


class ActionLogCollection(NailgunCollection):
    single = ActionLog
