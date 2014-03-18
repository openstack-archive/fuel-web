#!/usr/bin/env python
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

import __main__
import argparse
import code
import sys


def load_run_parsers(subparsers):
    run_parser = subparsers.add_parser(
        'run', help='run application locally'
    )
    run_parser.add_argument(
        '-p', '--port', dest='port', action='store', type=str,
        help='application port', default='8000'
    )
    run_parser.add_argument(
        '-a', '--address', dest='address', action='store', type=str,
        help='application address', default='0.0.0.0'
    )
    run_parser.add_argument(
        '--fake-tasks', action='store_true', help='fake tasks'
    )
    run_parser.add_argument(
        '--fake-tasks-amqp', action='store_true',
        help='fake tasks with real AMQP'
    )
    run_parser.add_argument(
        '--keepalive',
        action='store_true',
        help='run keep alive thread'
    )
    run_parser.add_argument(
        '-c', '--config', dest='config_file', action='store', type=str,
        help='custom config file', default=None
    )
    run_parser.add_argument(
        '--fake-tasks-tick-count', action='store', type=int,
        help='Fake tasks tick count'
    )
    run_parser.add_argument(
        '--fake-tasks-tick-interval', action='store', type=int,
        help='Fake tasks tick interval in seconds'
    )


def load_db_parsers(subparsers):
    subparsers.add_parser(
        'syncdb', help='sync application database'
    )
    subparsers.add_parser(
        'dropdb', help='drop application database'
    )
    # fixtures
    loaddata_parser = subparsers.add_parser(
        'loaddata', help='load data from fixture'
    )
    loaddata_parser.add_argument(
        'fixture', action='store', help='json fixture to load'
    )
    dumpdata_parser = subparsers.add_parser(
        'dumpdata', help='dump models as fixture'
    )
    dumpdata_parser.add_argument(
        'model', action='store', help='model name to dump; underscored name'
        'should be used, e.g. network_group for NetworkGroup model'
    )
    subparsers.add_parser(
        'loaddefault',
        help='load data from default fixtures '
             '(settings.FIXTURES_TO_IPLOAD)'
    )


def load_alembic_parsers(migrate_parser):
    alembic_parser = migrate_parser.add_subparsers(
        dest="alembic_command",
        help='alembic command'
    )
    for name in ['current', 'history', 'branches']:
        parser = alembic_parser.add_parser(name)

    for name in ['upgrade', 'downgrade']:
        parser = alembic_parser.add_parser(name)
        parser.add_argument('--delta', type=int)
        parser.add_argument('--sql', action='store_true')
        parser.add_argument('revision', nargs='?')

    parser = alembic_parser.add_parser('stamp')
    parser.add_argument('--sql', action='store_true')
    parser.add_argument('revision')

    parser = alembic_parser.add_parser('revision')
    parser.add_argument('-m', '--message')
    parser.add_argument('--autogenerate', action='store_true')
    parser.add_argument('--sql', action='store_true')


def load_db_migrate_parsers(subparsers):
    migrate_parser = subparsers.add_parser(
        'migrate', help='dealing with DB migration'
    )
    load_alembic_parsers(migrate_parser)


def load_test_parsers(subparsers):
    subparsers.add_parser(
        'test', help='run unit tests'
    )


def load_shell_parsers(subparsers):
    shell_parser = subparsers.add_parser(
        'shell', help='open python REPL'
    )
    shell_parser.add_argument(
        '-c', '--config', dest='config_file', action='store', type=str,
        help='custom config file', default=None
    )


def load_settings_parsers(subparsers):
    subparsers.add_parser(
        'dump_settings', help='dump current settings to YAML'
    )


def action_dumpdata(params):
    import logging

    logging.disable(logging.WARNING)
    from nailgun.db.sqlalchemy import fixman
    fixman.dump_fixture(params.model)
    sys.exit(0)


def action_loaddata(params):
    from nailgun.db.sqlalchemy import fixman
    from nailgun.logger import logger

    logger.info("Uploading fixture...")
    with open(params.fixture, "r") as fileobj:
        fixman.upload_fixture(fileobj)
    logger.info("Done")


def action_loaddefault(params):
    from nailgun.db.sqlalchemy import fixman
    from nailgun.logger import logger

    logger.info("Uploading fixture...")
    fixman.upload_fixtures()
    logger.info("Done")


def action_syncdb(params):
    from nailgun.db.migration import do_upgrade_head
    from nailgun.logger import logger

    logger.info("Syncing database...")
    do_upgrade_head()
    logger.info("Done")


def action_dropdb(params):
    from nailgun.db import dropdb
    from nailgun.logger import logger

    logger.info("Dropping database...")
    dropdb()
    logger.info("Done")


def action_migrate(params):
    from nailgun.db.migration import action_migrate_alembic
    action_migrate_alembic(params)


def action_test(params):
    from nailgun.logger import logger
    from nailgun.unit_test import TestRunner

    logger.info("Running tests...")
    TestRunner.run()
    logger.info("Done")


def action_dump_settings(params):
    from nailgun.settings import settings
    sys.stdout.write(settings.dump())


def action_shell(params):
    from nailgun.db import db
    from nailgun.settings import settings

    if params.config_file:
        settings.update_from_file(params.config_file)
    try:
        from IPython import embed
        embed()
    except ImportError:
        code.interact(local={'db': db, 'settings': settings})


def action_run(params):
    from nailgun.settings import settings

    settings.update({
        'LISTEN_PORT': int(params.port),
        'LISTEN_ADDRESS': params.address,
    })
    for attr in ['FAKE_TASKS', 'FAKE_TASKS_TICK_COUNT',
                 'FAKE_TASKS_TICK_INTERVAL', 'FAKE_TASKS_AMQP']:
        param = getattr(params, attr.lower())
        if param is not None:
            settings.update({attr: param})
    if params.config_file:
        settings.update_from_file(params.config_file)
    from nailgun.app import appstart
    appstart()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(
        dest="action", help='actions'
    )

    load_run_parsers(subparsers)
    load_db_parsers(subparsers)
    load_db_migrate_parsers(subparsers)
    load_test_parsers(subparsers)
    load_shell_parsers(subparsers)
    load_settings_parsers(subparsers)

    params, other_params = parser.parse_known_args()
    sys.argv.pop(1)

    action = getattr(
        __main__,
        "action_{0}".format(params.action)
    )
    action(params) if action else parser.print_help()
