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

# NOTE(eli): this is the name of table which was added
# in Fuel 7.0 in order to migrate the data from the core
# into extensions. This "shared" table allows us not
# not hardcode information about tables which are specific
# for extension or core into extension's and core's migrations.
extensions_migration_buffer_table_name = 'extensions_migration_buffer'

EXTENSIONS_NAMESPACE = 'nailgun.extensions'
