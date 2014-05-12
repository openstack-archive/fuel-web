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


ALEMBIC_CONFIG = alembic_config.Config(
    os.path.join(os.path.dirname(__file__), 'alembic.ini')
)
ALEMBIC_CONFIG.set_main_option(
    'script_location',
    'nailgun.db.migration:alembic_migrations'
)
ALEMBIC_CONFIG.set_main_option(
    'sqlalchemy.url',
    db_str
)


def do_alembic_command(cmd, *args, **kwargs):
    try:
        getattr(alembic_command, cmd)(ALEMBIC_CONFIG, *args, **kwargs)
    except alembic_util.CommandError as e:
        alembic_util.err(str(e))


def do_stamp(cmd):
    do_alembic_command(
        cmd,
        ALEMBIC_CONFIG.params.revision,
        sql=ALEMBIC_CONFIG.params.sql
    )


def do_revision(cmd):
    do_alembic_command(
        cmd,
        message=ALEMBIC_CONFIG.params.message,
        autogenerate=ALEMBIC_CONFIG.params.autogenerate,
        sql=ALEMBIC_CONFIG.params.sql
    )


def do_upgrade_downgrade(cmd):
    params = ALEMBIC_CONFIG.params
    if not params.revision and not params.delta:
        raise SystemExit('You must provide a revision or relative delta')

    if params.delta:
        sign = '+' if params.name == 'upgrade' else '-'
        revision = sign + str(params.delta)
    else:
        revision = params.revision

    do_alembic_command(cmd, revision, sql=params.sql)


def do_upgrade_head():
    do_alembic_command("upgrade", "head")


def action_migrate_alembic(params):
    global ALEMBIC_CONFIG
    ALEMBIC_CONFIG.params = params

    actions = {
        'current': do_alembic_command,
        'history': do_alembic_command,
        'branches': do_alembic_command,
        'upgrade': do_upgrade_downgrade,
        'downgrade': do_upgrade_downgrade,
        'stamp': do_stamp,
        'revision': do_revision
    }

    actions[params.alembic_command](params.alembic_command)


def drop_migration_meta(engine):
    engine.execute("DROP TABLE IF EXISTS alembic_version")
