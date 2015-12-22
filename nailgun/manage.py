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
import os
import sys


def add_config_parameter(parser):
    parser.add_argument(
        '-c', '--config', dest='config_file', action='store', type=str,
        help='custom config file', default=None
    )


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
    add_config_parameter(run_parser)
    run_parser.add_argument(
        '--fake-tasks-tick-count', action='store', type=int,
        help='Fake tasks tick count'
    )
    run_parser.add_argument(
        '--fake-tasks-tick-interval', action='store', type=int,
        help='Fake tasks tick interval in seconds'
    )
    run_parser.add_argument(
        '--authentication-method', action='store', type=str,
        help='Choose authentication type',
        choices=['none', 'fake', 'keystone'],
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
        'model', action='store', help='model name to dump; SQLAlchemy model '
        'name should be used, e.g. NetworkGroup for network_groups table'
    )
    generate_parser = subparsers.add_parser(
        'generate_nodes_fixture', help='generate new nodes fixture'
    )
    generate_parser.add_argument(
        '-n', '--total-nodes', dest='total_nodes', action='store', type=int,
        help='total nodes count to generate', required=True
    )
    generate_parser.add_argument(
        '-e', '--error-nodes', dest='error_nodes', action='store', type=int,
        help='error nodes count to generate'
    )
    generate_parser.add_argument(
        '-o', '--offline-nodes', dest='offline_nodes', action='store', type=int,
        help='offline nodes count to generate'
    )
    generate_parser.add_argument(
        '-i', '--min-ifaces-num', dest='min_ifaces_num', action='store',
        type=int, default=1,
        help='minimal number of ethernet interfaces for node'
    )
    subparsers.add_parser(
        'loaddefault',
        help='load data from default fixtures (settings.FIXTURES_TO_UPLOAD) '
             'and apply fake deployment tasks for all releases in database'
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


def load_dbshell_parsers(subparsers):
    dbshell_parser = subparsers.add_parser(
        'dbshell', help='open database shell'
    )
    add_config_parameter(dbshell_parser)


def load_test_parsers(subparsers):
    subparsers.add_parser(
        'test', help='run unit tests'
    )


def load_shell_parsers(subparsers):
    shell_parser = subparsers.add_parser(
        'shell', help='open python REPL'
    )
    add_config_parameter(shell_parser)


def load_settings_parsers(subparsers):
    subparsers.add_parser(
        'dump_settings', help='dump current settings to YAML'
    )


def load_extensions_parsers(subparsers):
    extensions_parser = subparsers.add_parser(
        'extensions', help='extensions related actions')

    load_alembic_parsers(extensions_parser)


def action_dumpdata(params):
    import logging

    logging.disable(logging.WARNING)
    from nailgun.db.sqlalchemy import fixman
    fixman.dump_fixture(params.model)
    sys.exit(0)


def action_generate_nodes_fixture(params):
    try:
        from oslo.serialization import jsonutils
    except ImportError:
        from oslo_serialization import jsonutils
    from nailgun.logger import logger
    from nailgun.utils import fake_generator

    logger.info('Generating new nodes fixture...')
    total_nodes_count = params.total_nodes
    fixtures_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                'nailgun/fixtures/')
    file_path = os.path.join(
        fixtures_dir,
        '{0}_fake_nodes_environment.json'.format(total_nodes_count)
    )
    generator = fake_generator.FakeNodesGenerator()
    res = generator.generate_fake_nodes(
        total_nodes_count, error_nodes_count=params.error_nodes,
        offline_nodes_count=params.offline_nodes,
        min_ifaces_num=params.min_ifaces_num)

    with open(file_path, 'w') as file_to_write:
        jsonutils.dump(res, file_to_write, indent=4)

    logger.info('Done. New fixture was stored in {0} file'.format(file_path))


def action_loaddata(params):
    from nailgun.db.sqlalchemy import fixman
    from nailgun.logger import logger

    logger.info("Uploading fixture...")
    with open(params.fixture, "r") as fileobj:
        fixman.upload_fixture(fileobj)
    logger.info("Done")


def action_loadfakedeploymenttasks(params):
    from nailgun.db.sqlalchemy import fixman
    from nailgun.logger import logger

    logger.info("Applying fake deployment tasks to all releases...")
    fixman.load_fake_deployment_tasks()
    logger.info("Done")


def action_loaddefault(params):
    from nailgun.db.sqlalchemy import fixman
    from nailgun.logger import logger

    logger.info("Uploading fixture...")
    fixman.upload_fixtures()
    logger.info("Applying fake deployment tasks to all releases...")
    fixman.load_fake_deployment_tasks()
    logger.info("Done")


def action_syncdb(params):
    from nailgun.db import syncdb
    from nailgun.logger import logger

    logger.info("Syncing database...")
    syncdb()
    logger.info("Done")


def action_dropdb(params):
    from nailgun.db import dropdb
    from nailgun.logger import logger

    logger.info("Dropping database...")
    dropdb()
    logger.info("Done")


def action_migrate(params):
    from nailgun.db.migration import action_migrate_alembic_core
    action_migrate_alembic_core(params)


def action_extensions(params):
    from nailgun.logger import logger
    from nailgun.db.migration import action_migrate_alembic_extension
    from nailgun.extensions import get_all_extensions

    for extension in get_all_extensions():
        if extension.alembic_migrations_path():
            logger.info('Running command for extension {0}'.format(
                extension.full_name()))
            action_migrate_alembic_extension(params, extension=extension)
        else:
            logger.info(
                'Extension {0} does not have migrations. '
                'Skipping...'.format(extension.full_name()))


def action_test(params):
    from nailgun.logger import logger
    from nailgun.unit_test import TestRunner

    logger.info("Running tests...")
    TestRunner.run()
    logger.info("Done")


def action_dbshell(params):
    from nailgun.settings import settings

    if params.config_file:
        settings.update_from_file(params.config_file)

    args = ['psql']
    env = {}
    if settings.DATABASE['passwd']:
        env['PGPASSWORD'] = settings.DATABASE['passwd']
    if settings.DATABASE['user']:
        args += ["-U", settings.DATABASE['user']]
    if settings.DATABASE['host']:
        args.extend(["-h", settings.DATABASE['host']])
    if settings.DATABASE['port']:
        args.extend(["-p", str(settings.DATABASE['port'])])
    args += [settings.DATABASE['name']]
    if os.name == 'nt':
        sys.exit(os.system(" ".join(args)))
    else:
        os.execvpe('psql', args, env)


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

    if params.authentication_method:
        auth_method = params.authentication_method
        settings.AUTH.update({'AUTHENTICATION_METHOD': auth_method})

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
    load_dbshell_parsers(subparsers)
    load_test_parsers(subparsers)
    load_shell_parsers(subparsers)
    load_settings_parsers(subparsers)
    load_extensions_parsers(subparsers)

    params, other_params = parser.parse_known_args()
    sys.argv.pop(1)

    action = getattr(
        __main__,
        "action_{0}".format(params.action)
    )
    action(params) if action else parser.print_help()
