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

from nailgun.api.v1.validators.base import BasicValidator
from nailgun.errors import errors


class TaskValidator(BasicValidator):

    @classmethod
    def validate_delete(cls, instance, force=False):
        if instance.status not in (
            consts.TASK_STATUSES.ready,
            consts.TASK_STATUSES.error
        ) and not force:
            raise errors.CannotDelete(
                "You cannot delete running task manually"
            )

    @classmethod
    def validate_update(cls, data, instance):
        return super(TaskValidator, cls).validate(data)
