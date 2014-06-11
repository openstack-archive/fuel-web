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


from nailgun.test import base
from nailgun.db import migration


class TestDbMigrations(base.BaseTestCase):

    def test_upgrade_downgrade_db_migrations(self):
        """Test verifies that database state isnt corrupted if
        after running: upgrade head > downgrade base sequence
        """
        migration.do_upgrade_head()
        migration.do_downgrade_base()
        migration.do_upgrade_head()
