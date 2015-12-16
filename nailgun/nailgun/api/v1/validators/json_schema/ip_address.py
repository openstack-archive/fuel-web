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

import copy

from nailgun.api.v1.validators.json_schema import base_types


IP_ADDRESS_UPDATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "id": {"type": "integer"},  # can't be updated via API
        "ip_addr": base_types.NULLABLE_IP_ADDRESS,
        "is_user_defined": {"type": "boolean"},
        "vip_name": {"type": "string"},  # can't be updated via API
    }
}


IP_ADDRESSES_UPDATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "array",
    "items": IP_ADDRESS_UPDATE_SCHEMA
}

# _IP_ADDRESS_SCHEMA currently not used and preserved
# to illustrate IP address fields
_IP_ADDRESS_SCHEMA = copy.deepcopy(IP_ADDRESS_UPDATE_SCHEMA)

_IP_ADDRESS_SCHEMA.update({
    "required": [
        "network",
        "ip_addr"
    ],
    "properties": {
        "network": base_types.NULLABLE_ID,
        "node": base_types.NULLABLE_ID
    }
})

_IP_ADDRESSES_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "array",
    "items": _IP_ADDRESS_SCHEMA
}
