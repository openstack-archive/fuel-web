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

import os

from alembic import command as alembic_command
from alembic import config as alembic_config
from alembic import util as alembic_util

from nailgun.db.sqlalchemy import db_str


def make_alembic_config(script_location, version_table):
    config = alembic_config.Config(
        os.path.join(os.path.dirname(__file__), 'alembic.ini'))
    config.set_main_option('script_location', script_location)
    config.set_main_option('sqlalchemy.url', db_str)
    config.set_main_option('version_table', version_table)

    return config


# Alembic config for core components
ALEMBIC_CONFIG = make_alembic_config(
    'nailgun.db.migration:alembic_migrations',
    'alembic_version')


def do_alembic_command(cmd, config, *args, **kwargs):
    try:
        getattr(alembic_command, cmd)(config, *args, **kwargs)
    except alembic_util.CommandError as e:
        alembic_util.err(str(e))


def do_stamp(cmd, config):
    do_alembic_command(
        cmd,
        config,
        config.params.revision,
        sql=config.params.sql)


def do_revision(cmd, config):
    do_alembic_command(
        cmd,
        config,
        message=config.params.message,
        autogenerate=config.params.autogenerate,
        sql=config.params.sql)


def do_upgrade_downgrade(cmd, config):
    params = config.params
    if not params.revision and not params.delta:
        raise SystemExit('You must provide a revision or relative delta')

    if params.delta:
        sign = '+' if params.name == 'upgrade' else '-'
        revision = sign + str(params.delta)
    else:
        revision = params.revision

    do_alembic_command(cmd, config, revision, sql=params.sql)


def do_upgrade_head(config=ALEMBIC_CONFIG):
    do_alembic_command("upgrade", config, "head")


def action_migrate_alembic(params, extension=None):
    if extension:
        config = make_alembic_config(
            extension.alembic_migrations_path(),
            extension.alembic_table_version())
    else:
        global ALEMBIC_CONFIG
        config = ALEMBIC_CONFIG

    config.params = params

    actions = {
        'current': do_alembic_command,
        'history': do_alembic_command,
        'branches': do_alembic_command,
        'upgrade': do_upgrade_downgrade,
        'downgrade': do_upgrade_downgrade,
        'stamp': do_stamp,
        'revision': do_revision
    }

    actions[params.alembic_command](params.alembic_command, config)


def drop_migration_meta(engine):
    engine.execute("DROP TABLE IF EXISTS alembic_version")
