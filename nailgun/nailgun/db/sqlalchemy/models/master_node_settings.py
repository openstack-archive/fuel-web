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

from slqalchemy import Column
from slqalchemy import String

from nailgun.db.sqlalchemy.models import Base
from nailgun.db.sqlalchemy.models.fields import JSON


class MasterNodeSettings(Base):
    __tablename__ = 'master_node_settings'

    master_node_uid = Column(String(36), primary_key=True)
    settings = Column(JSON, default={})
