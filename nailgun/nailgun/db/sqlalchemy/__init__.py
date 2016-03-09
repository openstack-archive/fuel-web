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
from sqlalchemy import schema

from sqlalchemy import MetaData
from sqlalchemy.engine import reflection
from sqlalchemy.orm import scoped_session
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.query import Query
from sqlalchemy import sql

from nailgun.db import deadlock_detector as dd
from nailgun.db.sqlalchemy import utils
from nailgun.settings import settings


db_str = utils.make_dsn(**settings.DATABASE)
engine = create_engine(db_str, client_encoding='utf8',
                       isolation_level=settings.DATABASE['isolation_level'])


class DeadlocksSafeQueryMixin(object):
    """Introduces ordered by id bulk deletes and updates into Query

    """

    def _get_tables(self):
        """ Extracts table names from Query

        :return: generator to collection of strings
        """
        for ent in self._entities:
            yield '{0}'.format(ent.selectable)

    def _trace_ids(self, *args, **kwargs):
        """Bulk deletion with ascending order by id

        Ordered by ids UPDATE and DELETE are not supported by SQL standard.
        As workaround we just lock records before bulk deletion or updating
        and add trace selected ids in the appropriate deadlock_detector.Lock
        """

        # Only one table is used for DELETE and UPDATE query
        table = next(self._get_tables())
        columns = ['id']
        if self.whereclause is not None:
            # Creating ordered by id select query with whereclause from
            # origin query
            query_select = sql.expression.select(
                columns=columns, whereclause=self.whereclause)
        else:
            query_select = sql.expression.select(
                columns=columns, from_obj=table)

        query_select = query_select.order_by('id').with_for_update()
        result = db().execute(query_select)

        # We should trace locked ids only when deadlock detection activated
        if settings.DEVELOPMENT:
            dd.handle_lock(
                table, [row[0] for row in result.fetchall()])

    def delete(self, *args, **kwargs):
        self._trace_ids(*args, **kwargs)
        super(DeadlocksSafeQueryMixin, self).delete(*args, **kwargs)

    def update(self, *args, **kwargs):
        self._trace_ids(*args, **kwargs)
        super(DeadlocksSafeQueryMixin, self).update(*args, **kwargs)


class DeadlockDetectingQuery(DeadlocksSafeQueryMixin, Query):

    def with_lockmode(self, mode):
        """with_lockmode function wrapper for deadlock detection
        """
        for table in self._get_tables():
            dd.register_lock(table)
        return super(DeadlockDetectingQuery, self).with_lockmode(mode)

    def with_for_update(self, *args, **kwargs):
        for table in self._get_tables():
            dd.register_lock(table)
        return super(DeadlockDetectingQuery, self).with_for_update(*args, **kwargs)

    def _is_locked_for_update(self):
        return self._for_update_arg is not None \
            and self._for_update_arg.read is False \
            and self._for_update_arg.nowait is False

    def all(self):
        result = super(DeadlockDetectingQuery, self).all()
        if self._is_locked_for_update():
            for table in self._get_tables():
                lock = dd.find_lock(table)
                lock.add_ids(o.id for o in result)
        return result

    def _trace_single_row(self, row):
        if self._is_locked_for_update():
            for table in self._get_tables():
                lock = dd.find_lock(table)
                if row is not None:
                    lock.add_ids((row.id,))

    def first(self):
        result = super(DeadlockDetectingQuery, self).first()
        self._trace_single_row(result)
        return result

    def one(self):
        result = super(DeadlockDetectingQuery, self).one()
        self._trace_single_row(result)
        return result

    def get(self, ident):
        result = super(DeadlockDetectingQuery, self).get(ident)
        self._trace_single_row(result)
        return result


class DeadlockDetectingSession(Session):
    """This session class is used for deadlocks detection."""

    def commit(self):
        dd.clean_locks()
        super(DeadlockDetectingSession, self).commit()

    def rollback(self):
        dd.clean_locks()
        super(DeadlockDetectingSession, self).rollback()

    def delete(self, instance):
        super(DeadlockDetectingSession, self).delete(instance)
        dd.handle_lock(instance.__tablename__,
                       ids=(instance.id,))


# We introduce deadlock detection workflow only for
# development mode
if settings.DEVELOPMENT:
    query_class = DeadlockDetectingQuery
    session_class = DeadlockDetectingSession
else:
    query_class = Query
    session_class = Session

db = scoped_session(
    sessionmaker(
        autoflush=True,
        autocommit=False,
        bind=engine,
        query_cls=query_class,
        class_=session_class
    )
)


def syncdb():
    from nailgun.db.migration import do_upgrade_head
    do_upgrade_head()


def dropdb():
    from nailgun.db import migration
    conn = engine.connect()
    trans = conn.begin()
    meta = MetaData()
    meta.reflect(bind=engine)
    inspector = reflection.Inspector.from_engine(engine)

    tbs = []
    all_fks = []

    for table_name in inspector.get_table_names():
        fks = []
        for fk in inspector.get_foreign_keys(table_name):
            if not fk['name']:
                continue
            fks.append(
                schema.ForeignKeyConstraint((), (), name=fk['name'])
            )
        t = schema.Table(
            table_name,
            meta,
            *fks,
            extend_existing=True
        )
        tbs.append(t)
        all_fks.extend(fks)

    for fkc in all_fks:
        conn.execute(schema.DropConstraint(fkc))

    for table in tbs:
        conn.execute(schema.DropTable(table))

    custom_types = conn.execute(
        "SELECT n.nspname as schema, t.typname as type "
        "FROM pg_type t LEFT JOIN pg_catalog.pg_namespace n "
        "ON n.oid = t.typnamespace "
        "WHERE (t.typrelid = 0 OR (SELECT c.relkind = 'c' "
        "FROM pg_catalog.pg_class c WHERE c.oid = t.typrelid)) "
        "AND NOT EXISTS(SELECT 1 FROM pg_catalog.pg_type el "
        "WHERE el.oid = t.typelem AND el.typarray = t.oid) "
        "AND     n.nspname NOT IN ('pg_catalog', 'information_schema')"
    )

    for tp in custom_types:
        conn.execute("DROP TYPE {0}".format(tp[1]))
    trans.commit()
    migration.drop_migration_meta(engine)
    conn.close()
    engine.dispose()


def flush():
    """Delete all data from all tables within nailgun metadata
    """
    from nailgun.db.sqlalchemy.models.base import Base
    with contextlib.closing(engine.connect()) as con:
        trans = con.begin()
        for table in reversed(Base.metadata.sorted_tables):
            con.execute(table.delete())
        trans.commit()
