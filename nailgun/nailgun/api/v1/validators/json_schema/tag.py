# -*- coding: utf-8 -*-
#    Copyright 2016 Mirantis, Inc.
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

TAG_META_INFO = {
    "type": "object",
    "required": ["has_primary"],
    "properties": {
        "has_primary": {
            "type": "boolean",
            "description": ("During orchestration this role"
                            " will be splitted into primary-role and role.")
        }
    }
}


SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "title": "Tag",
    "description": "Serialized Tag object",
    "type": "object",
    "required": ['name'],
    "properties": {
        "name": {"type": "string", "pattern": "^[a-zA-Z0-9_-]+$"},
        "meta": TAG_META_INFO
    }
}
