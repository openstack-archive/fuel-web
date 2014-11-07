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

from psycopg2 import connect

from nailgun.settings import settings


def pytest_addoption(parser):
    parser.addoption("--dbname", default=settings.DATABASE['name'],
                     help="Overwrite database name")


def pytest_configure(config):
    db_name = config.getoption('dbname')
    if hasattr(config, 'slaveinput'):
        slaveid = config.slaveinput['slaveid']
        db_name = '{0}_{1}'.format(db_name, slaveid)
        # can use postgres here, any opinions?
        connection = connect(
            dbname='nailgun', user=settings.DATABASE['user'],
            host=settings.DATABASE['host'],
            password=settings.DATABASE['passwd'])
        cursor = connection.cursor()
        if not_present(cursor, db_name):
            create_database(connection, cursor, db_name)
    settings.DATABASE['name'] = db_name


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
