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

import inspect
import os
import pkgutil

from contextlib import nested
from datetime import datetime

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


def do_squash(cmd):
    params = ALEMBIC_CONFIG.params
    script_location = ALEMBIC_CONFIG.get_main_option("script_location")
    script_dir = os.path.join(
        os.path.dirname(ALEMBIC_CONFIG.config_file_name),
        script_location.split(":")[-1],
    )
    m_dir = os.path.join(script_dir, 'versions')
    m_package = script_location.replace(":", ".") + ".versions"
    m_template = os.path.join(script_dir, 'migration.template')

    mig_map = {}

    for _, name, _ in pkgutil.iter_modules([m_dir]):
        mod = getattr(__import__(m_package, fromlist=[name]), name)
        if hasattr(mod, "down_revision") and hasattr(mod, "revision"):
            mig_map[mod.down_revision] = (mod.revision, mod)

    if None not in mig_map:
        raise Exception("Can't find starting migration!")

    migrations = []
    prev = None
    while True:
        migrations.append(mig_map[prev][1])
        prev = mig_map[prev][0]
        if prev not in mig_map:
            break

    last_revision = migrations[-1].revision
    upgrade_declaration = "def upgrade():\n"
    downgrade_declaration = "def downgrade():\n"

    squashed_upgrade = []
    squashed_downgrade = []
    for m in migrations:
        for line in inspect.getsourcelines(m.upgrade)[0][1:]:
            squashed_upgrade.append(line)
        for line in inspect.getsourcelines(m.downgrade)[0][1:]:
            squashed_downgrade.append(line)

    if params.drop_original:
        for _, name, _ in pkgutil.iter_modules([m_dir]):
            os.unlink(os.path.join(m_dir, "{0}.py".format(name)))

    with nested(
        open(m_template, "r"),
        open(os.path.join(m_dir, "{0}.py".format(params.name)), "w")
    ) as (tmpl, mig):
        mig.write(
            tmpl.read().format(**{
                "message": "Migration {0}".format(params.name),
                "down_revision": None,
                "revision": last_revision,
                "datetime": datetime.now().strftime(
                    '%Y-%m-%d %H:%M:%S'
                )
            })
        )
        mig.write("\n\n")
        mig.write(upgrade_declaration)
        mig.write("".join(squashed_upgrade))
        mig.write("\n\n")
        mig.write(downgrade_declaration)
        mig.write("".join(squashed_downgrade))


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
        'revision': do_revision,
        'squash': do_squash
    }

    actions[params.alembic_command](params.alembic_command)
