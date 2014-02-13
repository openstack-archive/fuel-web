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

import pprint

from alembic import autogenerate
from alembic import migration

from nailgun.test import base
from nailgun.db import sqlalchemy


class TestMigrationsInSync(base.BaseIntegrationTest):

    def test_migrations_in_sync_with_metadata(self):
        """Uses same tools that enables autogeneration of migration scripts
        """
        metadata = sqlalchemy.models.base.Base.metadata
        engine = sqlalchemy.engine

        migration_context = migration.MigrationContext.configure(
            engine.connect())

        diff = autogenerate.compare_metadata(migration_context, metadata)

        if diff:
            formated_diff = pprint.pformat(diff, indent=2, width=20)

            self.fail('Migration arent in sync '
                      'with database state:\n{0}'.format(formated_diff))




