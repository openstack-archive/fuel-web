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

from datetime import datetime

from sqlalchemy import func

from nailgun import consts
from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun import errors
from nailgun.logger import logger
from nailgun.objects import NailgunCollection
from nailgun.objects import NailgunObject
from nailgun.objects.serializers.notification import NotificationSerializer
from nailgun.objects import Task


class Notification(NailgunObject):

    model = models.Notification
    serializer = NotificationSerializer

    @classmethod
    def create(cls, data):
        """Creates and returns a notification instance.

        :param data: a dict with notification data
        :returns: a notification instance in case of notification
            doesn't exist; otherwise - None
        """
        topic = data.get("topic")
        node_id = data.get("node_id")
        task_uuid = data.pop("task_uuid", None)
        message = data.get("message")

        if topic == 'discover' and node_id is None:
            raise errors.CannotFindNodeIDForDiscovering(
                "No node id in discover notification"
            )

        if "datetime" not in data:
            data["datetime"] = datetime.now()

        exist = None
        if task_uuid:
            task = Task.get_by_uuid(task_uuid)
            if task and node_id:
                exist = NotificationCollection.count(
                    NotificationCollection.filter_by(
                        None,
                        node_id=node_id,
                        message=message,
                        task_id=task.id
                    )
                )

        if not exist:
            notification = super(Notification, cls).create(data)
            logger.info(
                u"Notification: topic: {0} message: {1}".format(
                    data.get("topic"),
                    data.get("message")
                )
            )
            return notification
        return None

    @classmethod
    def to_dict(cls, instance, fields=None, serializer=None):
        serializer = serializer or cls.serializer
        notif_dict = serializer.serialize(instance, fields=fields)
        notif_dict['time'] = instance.datetime.strftime('%H:%M:%S')
        notif_dict['date'] = instance.datetime.strftime('%d-%m-%Y')
        return notif_dict

    @classmethod
    def get_statuses_with_count(cls):
        """Counts notifications statuses in DB

        Calculates total number of notifications and adds it to the
        result. Count of unread notifications and total are mandatory
        fields

        :return: dict of {'total': count, 'unread': count, ...}
        """
        result = dict.fromkeys(consts.NOTIFICATION_STATUSES, 0)
        query = db().query(cls.model.status, func.count(cls.model.status)).\
            group_by(cls.model.status)
        for status, num in query.all():
            result[status] = num
        result['total'] = sum(result.values())
        return result


class NotificationCollection(NailgunCollection):

    single = Notification
