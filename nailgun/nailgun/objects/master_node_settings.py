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


from nailgun.objects.base import NailgunObject
from nailgun.objects.serializers.master_node_settings \
    import MasterNodeSettingsSerializer

from nailgun.db.sqlalchemy.models import MasterNodeSettings


class MasterNodeSettings(NailgunObject):

    model = MasterNodeSettings

    serializer = MasterNodeSettingsSerializer

    schema = {
        "$schema": "http://json-schema.org/draft-04/schema#",
        "title": "ActionLog",
        "description": "Serialized ActionLog object",
        "type": "object",
        "properties": {
            "settings": {
                "type": "object",
                "properties": {
                    "send_anonymous_statistic": {"type": "boolean"},
                    "send_user_info": {"type": "boolean"},
                    "user_info": {
                        "type": "object",
                        "properties": {
                            "user_name": {"type": "string"},
                            "user_email": {
                                "type": "string",
                                "format": "email"
                            }
                        }
                    }
                }
            }
        }
    }

    validator = None
