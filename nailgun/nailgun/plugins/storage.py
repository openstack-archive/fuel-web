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

from sqlalchemy import orm

from sqlalchemy import Integer
from sqlalchemy import String

#from sqlalchemy.dialects.postgresql import JSON

from nailgun.db import engine
from nailgun.db import NoCacheQuery

from nailgun.db.sqlalchemy.models import PluginRecord


class PluginStorage(object):

    model = PluginRecord

    type_mappings = {
        "node_id": Integer,
        "disk_id": String,
        "name": String,
        #"data": JSON
    }

    def __init__(self, plugin_name):
        self.plugin_name = plugin_name
        self.db = orm.scoped_session(
            orm.sessionmaker(bind=engine, query_cls=NoCacheQuery)
        )()

    def __enter__(self):
        return self

    def __exit__(self, tp, value, traceback):
        self.db.commit()

    def add_record(self, record_type, data):
        new_record = self.model(
            plugin=self.plugin_name,
            record_type=record_type,
            data=data
        )
        self.db.add(new_record)
        self.db.flush()
        return new_record.id

    def drop_record(self, record_id):
        record = self.db.query(self.model).get(record_id)
        if record:
            self.db.delete(record)
            self.db.flush()

    def search_records(self, record_type=None, **kwargs):
        records = self.db.query(self.model).filter_by(
            plugin=self.plugin_name,
            record_type=record_type,
        )

        for field in kwargs.iterkeys():
            if field in self.type_mappings:
                records = records.filter(
                    self.model.data[field].cast(
                        self.type_mappings[field]
                    ) == kwargs[field]
                )
        return records.all()
