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
import copy

from nailgun.api.v1.validators.json_schema.base_types import MAC_ADDRESS

from nailgun.api.v1.validators.json_schema.node import NODE


# GET schema
GET_REQUEST = {}

GET_RESPONSE = {
    'type': 'array',
    'items': NODE
}

# POST schema
POST_REQUEST = copy.deepcopy(NODE)
POST_REQUEST['properties'].update({
    'mac': MAC_ADDRESS
})
POST_REQUEST['required'] = ['mac']
POST_REQUEST['additionalProperties'] = False

POST_RESPONSE = copy.deepcopy(NODE)
