# -*- coding: utf-8 -*-

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

"""
CapacityLog objects
"""

from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun.objects import NailgunObject


class CapacityLog(NailgunObject):

    model = models.CapacityLog

    @classmethod
    def get_latest(cls):
        return db().query(cls.model).order_by(
            cls.model.datetime.desc()
        ).first()
