# -*- coding: utf-8 -*-

#    Copyright 2013 Mirantis, Inc.
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

import contextlib
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.orm.query import Query

from nailgun.settings import settings


db_str = "{engine}://{user}:{passwd}@{host}:{port}/{name}".format(
    **settings.DATABASE)


engine = create_engine(db_str, client_encoding='utf8')

class NoCacheQuery(Query):
    """Override for common Query class.
    Needed for automatic refreshing objects
    from database during every query for evading
    problems with multiple sessions
    """
    def __init__(self, *args, **kwargs):
        self._populate_existing = True
        super(NoCacheQuery, self).__init__(*args, **kwargs)


db = scoped_session(
    sessionmaker(
        autoflush=True,
        autocommit=False,
        bind=engine,
        query_cls=NoCacheQuery
    )
)


def syncdb():
    from nailgun.db.migration import do_upgrade_head
    do_upgrade_head()


def dropdb():
    from nailgun.db import migration
    from nailgun.db.sqlalchemy.models.base import Base
    Base.metadata.drop_all(bind=engine)
    migration.drop_migration_meta(engine)


def flush():
    """Delete all data from all tables within nailgun metadata
    """
    from nailgun.db.sqlalchemy.models.base import Base
    with contextlib.closing(engine.connect()) as con:
        trans = con.begin()
        for table in reversed(Base.metadata.sorted_tables):
            con.execute(table.delete())
        trans.commit()
