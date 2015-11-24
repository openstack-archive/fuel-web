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

from oslo_serialization import jsonutils
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy import Integer
from sqlalchemy import String

from nailgun.db.sqlalchemy.models.base import Base


class MasterNodeSettings(Base):
    __tablename__ = 'master_node_settings'

    id = Column(Integer, primary_key=True)
    master_node_uid = Column(String(36), nullable=False)
    settings = Column(
        MutableDict.as_mutable(JSON),
        nullable=False,
        server_default=jsonutils.dumps({
            "ui_settings": {
                "view_mode": "standard",
                "filter": {},
                "sort": [{"status": "asc"}],
                "filter_by_labels": {},
                "sort_by_labels": [],
                "search": ""
            }
        }),
    )
