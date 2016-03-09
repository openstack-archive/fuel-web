# -*- coding: utf-8 -*-

#    Copyright 2015 Mirantis, Inc.
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

import alembic

from nailgun import db
from nailgun.db.migration import make_alembic_config_from_extension
from nailgun.extensions.volume_manager.extension import VolumeManagerExtension
from nailgun.test import base


_test_revision = '086cde3de7cf'


def setup_module(module):
    alembic_config = make_alembic_config_from_extension(VolumeManagerExtension)
    db.dropdb()
    alembic.command.upgrade(alembic_config, _test_revision)


class TestAddVolumes(base.BaseAlembicMigrationTest):

    def test_works_without_core_migrations(self):
        columns = [
            t.name for t in
            self.meta.tables['volume_manager_node_volumes'].columns]

        self.assertItemsEqual(columns, ['id', 'node_id', 'volumes'])
