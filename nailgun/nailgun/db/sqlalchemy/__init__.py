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

from sqlalchemy.engine import reflection
from sqlalchemy.orm import scoped_session, sessionmaker
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

    conn = engine.connect()
    trans = conn.begin()

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
            Base.metadata,
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


def flush():
    """Delete all data from all tables within nailgun metadata
    """
    from nailgun.db.sqlalchemy.models.base import Base
    with contextlib.closing(engine.connect()) as con:
        trans = con.begin()
        for table in reversed(Base.metadata.sorted_tables):
            key_column_names = map(str, table.primary_key.columns)
            con.execute(table.select(order_by=key_column_names, for_update=True))
            con.execute(table.delete())
        trans.commit()
