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

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.query import Query

from nailgun.db.deadlock_detector import clean_locks
from nailgun.db.deadlock_detector import handle_lock
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


# Methods substitution for deadlock detecting
def with_lockmode_with_deadlock_detection(self, mode):
    """with_lockmode function wrapper for deadlock detection
    """
    for ent in self._entities:
        handle_lock('{0}'.format(ent.selectable))
    return self.with_lockmode_origin(mode)


Query.with_lockmode_origin = Query.with_lockmode
Query.with_lockmode = with_lockmode_with_deadlock_detection


def commit_with_deadlock_detection(self):
    """commit function wrapper for deadlock detection
    """
    clean_locks()
    self.commit_origin()


Session.commit_origin = Session.commit
Session.commit = commit_with_deadlock_detection


def rollback_with_deadlock_detection(self):
    """rollback function wrapper for deadlock detection
    """
    clean_locks()
    self.rollback_origin()


Session.rollback_origin = Session.rollback
Session.rollback = rollback_with_deadlock_detection
