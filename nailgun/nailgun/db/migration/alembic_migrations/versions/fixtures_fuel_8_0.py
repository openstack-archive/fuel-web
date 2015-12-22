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

"""Fixtures for Fuel 8.0

Revision ID: bd024cf27524
Revises: 43b2cb64dae6
Create Date: 2015-12-22 15:51:35.473193

"""

# revision identifiers, used by Alembic.

revision = 'bd024cf27524'
down_revision = None
branch_labels = ('fixtures', )


from nailgun.db.sqlalchemy import fixman


def upgrade():
    fixman.do_upload_fixtures()


def downgrade():
    # Nothing to do. We shouldn't remove fixtures from DB
    pass
