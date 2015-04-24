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

"""VXLAN support

Revision ID: 2eb3b90ab2fb
Revises: 37608259013
Create Date: 2015-06-09 15:35:01.968910

"""

# revision identifiers, used by Alembic.
revision = '2eb3b90ab2fb'
down_revision = '37608259013'


from nailgun import consts
from nailgun.utils.migration import upgrade_enum


def upgrade():

    segmentation_type_old = ('vlan', 'gre')
    segmentation_type_new = consts.NEUTRON_SEGMENT_TYPES

    upgrade_enum('neutron_config',
                 'segmentation_type',
                 'segmentation_type',
                 segmentation_type_old,
                 segmentation_type_new)


def downgrade():
    pass
