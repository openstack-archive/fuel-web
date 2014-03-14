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

from alembic import op
import sqlalchemy as sa


def upgrade_enum(table, column_name, enum_name, old_options, new_options):
    old_type = sa.Enum(*old_options, name=enum_name)
    new_type = sa.Enum(*new_options, name=enum_name)
    tmp_type = sa.Enum(*new_options, name="_" + enum_name)
    # Create a tempoary type, convert and drop the "old" type
    tmp_type.create(op.get_bind(), checkfirst=False)
    op.execute(
        u'ALTER TABLE {0} ALTER COLUMN {1} TYPE _{2}'
        u' USING {1}::text::_{2}'.format(
            table,
            column_name,
            enum_name
        )
    )
    old_type.drop(op.get_bind(), checkfirst=False)
    # Create and convert to the "new" type
    new_type.create(op.get_bind(), checkfirst=False)
    op.execute(
        u'ALTER TABLE {0} ALTER COLUMN {1} TYPE {2}'
        u' USING {1}::text::{2}'.format(
            table,
            column_name,
            enum_name
        )
    )
    tmp_type.drop(op.get_bind(), checkfirst=False)


def select_enums(enum_name):
    old = op.get_bind()\
        .execute('SELECT enum_range(NULL::{0});'.format(enum_name)).scalar()
    return set(e for e in re.split('\W+', old) if e)


def enum_select_and_upgrade(table, column_name, enum_name, added):
    old_options = select_enums(enum_name)
    new_options = old_options | set(added)
    upgrade_enum("tasks", "name", enum_name, old_options, new_options)


def enum_select_and_downgrade(table, column_name, enum_name, removed):
    old_options = select_enums(enum_name)
    new_options = old_options - set(removed)
    upgrade_enum("tasks", "name", enum_name, old_options, new_options)
