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

from alembic import op
import sqlalchemy as sa

import six


def upgrade_enum(table, column_name, enum_name, old_options, new_options):
    old_type = sa.Enum(*old_options, name=enum_name)
    new_type = sa.Enum(*new_options, name=enum_name)
    tmp_type = sa.Enum(*new_options, name="_" + enum_name)
    # Create a temporary type, convert and drop the "old" type
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


def drop_enum(name):
    op.execute(
        u'DROP TYPE {0}'.format(name)
    )


def convert_condition_value(val):
    if isinstance(val, six.string_types):
        return "'{0}'".format(val)
    return str(val).lower()


def upgrade_release_attributes_50_to_51(attrs_meta):
    if not attrs_meta.get('editable'):
        return attrs_meta

    def depends_to_restrictions(depends):
        for cond in depends:
            expr = cond.keys()[0]
            restrictions.append(
                expr + " != " + convert_condition_value(cond[expr]))

    def conflicts_to_restrictions(conflicts):
        for cond in conflicts:
            expr = cond.keys()[0]
            restrictions.append(
                expr + " == " + convert_condition_value(cond[expr]))

    for _, group in attrs_meta.get('editable').iteritems():
        for _, attr in group.iteritems():
            restrictions = []
            if attr.get('depends'):
                depends_to_restrictions(attr['depends'])
                attr.pop('depends')
            if attr.get('conflicts'):
                conflicts_to_restrictions(attr['conflicts'])
                attr.pop('conflicts')
            if restrictions:
                attr['restrictions'] = restrictions
    return attrs_meta


def upgrade_release_roles_50_to_51(roles_meta):
    for _, role in roles_meta.iteritems():
        if role.get('depends'):
            for depend in role['depends']:
                if isinstance(depend.get('condition'), dict):
                    cond = depend['condition']
                    expr = cond.keys()[0]
                    depend['condition'] = \
                        expr + " == " + convert_condition_value(cond[expr])
    return roles_meta
