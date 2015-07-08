# -*- coding: utf-8 -*-
#    Copyright 2015 Mirantis, Inc.
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


from nailgun.api.v1.validators.base import BasicValidator
from nailgun.api.v1.validators.json_schema import dashboard_entry
from nailgun.errors import errors
from nailgun.objects import DashboardEntry

class DashboardEntryValidator(BasicValidator):

    single_schema = dashboard_entry.DASHBOARD_ENTRY_SCHEMA
    collection_schema = dashboard_entry.DASHBOARD_ENTRIES_SCHEMA

    @classmethod
    def validate(cls, data):
        parsed = super(DashboardEntryValidator, cls).validate(data)
        cls.validate_schema(parsed, dashboard_entry.DASHBOARD_ENTRY_SCHEMA)
        return parsed

    @classmethod
    def validate_update(cls, data, instance):
        return cls.validate(data)

    @classmethod
    def validate_create(cls, data):
        return cls.validate(data)

