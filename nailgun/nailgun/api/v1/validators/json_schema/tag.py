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

TAG_CREATION_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "title": "Tag",
    "description": "Serialized Tag object",
    "type": "object",
    "properties": {
        "tag": {"type": "string"},
        "has_primary": {"type": "boolean"}
    },
    "required": ["tag"],
}

TAG_UPDATING_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "title": "Tag",
    "description": "Serialized Tag object",
    "type": "object",
    "properties": {
        "id": {"type": "integer"},
        "tag": {"type": "string"},
        "has_primary": {"type": "boolean"}
    }
}
