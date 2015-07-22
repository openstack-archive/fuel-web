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

from sqlalchemy.engine.reflection import Inspector

from nailgun.extensions.consts import extensions_migration_buffer_table_name


def is_buffer_table_exist(connection):
    """Performs check if buffer table exists in the database.

    :returns: True if table exists, False otherwise
    """
    inspector = Inspector.from_engine(connection)
    return (extensions_migration_buffer_table_name in
            inspector.get_table_names())
