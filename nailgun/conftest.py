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

import re

from psycopg2 import connect

from nailgun.settings import settings


def pytest_addoption(parser):
    parser.addoption("--dbname", default=settings.DATABASE['name'],
                     help="Overwrite database name")
    parser.addoption("--cleandb", default=False, action="store_true",
                     help="Provide this flag to dropdb/syncdb for all slaves")


def pytest_configure(config):
    db_name = config.getoption('dbname')
    if hasattr(config, 'slaveinput'):
        #slaveid have next format gw1
        #it is internal pytest thing, and we dont want to use it
        uid = re.search(r'\d+', config.slaveinput['slaveid']).group(0)
        db_name = '{0}{1}'.format(db_name, uid)
        connection = connect(
            dbname='postgres', user=settings.DATABASE['user'],
            host=settings.DATABASE['host'],
            password=settings.DATABASE['passwd'])
        cursor = connection.cursor()
        if not_present(cursor, db_name):
            create_database(connection, cursor, db_name)
    settings.DATABASE['name'] = db_name
    cleandb = config.getoption('cleandb')
    if cleandb:
        from nailgun.db import dropdb, syncdb
        dropdb()
        syncdb()


def pytest_unconfigure(config):
    cleandb = config.getoption('cleandb')
    if cleandb:
        from nailgun.db import dropdb
        dropdb()


def create_database(connection, cursor, name):
    connection.set_isolation_level(0)
    cursor.execute('create database {0}'.format(name))
    connection.set_isolation_level(1)
    cursor.close()
    connection.close()


def not_present(cur, name):
    cur.execute('select datname from pg_database;')
    db_list = cur.fetchall()
    return all([name not in row for row in db_list])
