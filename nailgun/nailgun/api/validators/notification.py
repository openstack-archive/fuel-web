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

from nailgun import consts
from nailgun import objects

from nailgun.api.validators.base import BasicValidator
from nailgun.errors import errors


class NotificationValidator(BasicValidator):
    @classmethod
    def validate_update(cls, data, instance):

        valid = {}
        d = cls.validate_json(data)

        status = d.get("status", None)
        if status in consts.NOTIFICATION_STATUSES:
            valid["status"] = status
        else:
            raise errors.InvalidData(
                "Bad status",
                log_message=True
            )

        return valid

    @classmethod
    def validate_collection_update(cls, data):
        d = cls.validate_json(data)
        if not isinstance(d, list):
            raise errors.InvalidData(
                "Invalid json list",
                log_message=True
            )

        valid_d = []
        for nd in d:
            valid_nd = {}
            if "id" not in nd:
                raise errors.InvalidData(
                    "ID is not set correctly",
                    log_message=True
                )

            if "status" not in nd:
                raise errors.InvalidData(
                    "ID is not set correctly",
                    log_message=True
                )

            if not objects.Notification.get_by_uid(nd["id"]):
                raise errors.InvalidData(
                    "Invalid ID specified",
                    log_message=True
                )

            valid_nd["id"] = nd["id"]
            valid_nd["status"] = nd["status"]
            valid_d.append(valid_nd)
        return valid_d

    @classmethod
    def validate_delete(cls, instance):
        """There's nothing to do right now. We just have to remove a given
        instance from database, without any validations.
        """
        pass
