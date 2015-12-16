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


IP_ADDR_UPDATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "object",
    "additionalProperties": False,
    # actually only `ip_addr` and `is_user_defined` is allowed to be updated
    # by validator business logic
    "properties": {
        "id": {"type": "integer"},
        "ip_addr": base_types.NULLABLE_IP_ADDRESS,
        "is_user_defined": {"type": "boolean"},
        "network": base_types.NULLABLE_ID,
        "node": base_types.NULLABLE_ID,
        "vip_name": {"type": "string"}
    }
}

IP_ADDR_UPDATE_WITH_ID_SCHEMA = copy.deepcopy(IP_ADDR_UPDATE_SCHEMA)
IP_ADDR_UPDATE_WITH_ID_SCHEMA["required"] = ["id"]

IP_ADDRS_UPDATE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "array",
    "items": IP_ADDR_UPDATE_WITH_ID_SCHEMA
}


# _IP_ADDRESS_SCHEMA currently not used and preserved
# to illustrate IP address fields
_IP_ADDR_SCHEMA = copy.deepcopy(IP_ADDR_UPDATE_SCHEMA)

_IP_ADDR_SCHEMA["required"] = ["network", "ip_addr"]

_IP_ADDRS_SCHEMA = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "type": "array",
    "items": _IP_ADDR_SCHEMA
}
