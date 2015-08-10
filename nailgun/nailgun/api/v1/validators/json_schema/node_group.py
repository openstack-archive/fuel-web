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


single_schema = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "title": "NetworkGroup",
    "description": "Serialized NetworkGroup object",
    "type": "object",
    "properties": {
        "cluster_id": {"type": "integer"},
        "name": {"type": "string"},
    },
    "required": ["cluster_id", "name"],
}
