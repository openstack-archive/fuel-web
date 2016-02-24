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

from copy import deepcopy

from nailgun.objects import Plugin
from nailgun.test.base import BaseTestCase
from nailgun.utils.migration import \
    upgrade_6_0_to_6_1_plugins_cluster_attrs_use_ids_mapping


class TestMigrationPluginsClusterAttrs(BaseTestCase):

    def setUp(self):
        super(TestMigrationPluginsClusterAttrs, self).setUp()
        self.env.create()
        self.cluster = self.env.clusters[0]
        self.plugins = [
            Plugin.create(self.env.get_default_plugin_metadata(
                name='plugin_name_1')),
            Plugin.create(self.env.get_default_plugin_metadata(
                name='plugin_name_2'))]

    def test_replaces_versions_with_ids(self):
        attrs = deepcopy(self.cluster.attributes.editable)

        for plugin in self.plugins:
            attrs[plugin.name] = {}
            attrs[plugin.name]['metadata'] = {
                'plugin_version': plugin.version}

        self.cluster.attributes.editable = attrs
        self.db.commit()

        connection = self.db.connection()
        upgrade_6_0_to_6_1_plugins_cluster_attrs_use_ids_mapping(connection)

        for plugin in self.plugins:
            plugin_attr = self.cluster.attributes.editable[plugin.name]

            self.assertEqual(plugin_attr['metadata']['plugin_id'], plugin.id)
            self.assertNotIn('plugin_version', plugin_attr['metadata'])

    def test_do_not_fail_if_plugin_was_not_found(self):
        attrs = deepcopy(self.cluster.attributes.editable)

        attrs['some_plugin_name'] = {}
        attrs['some_plugin_name']['metadata'] = {
            'plugin_version': '1111.111.111'}

        self.cluster.attributes.editable = attrs
        self.db.commit()
        connection = self.db.connection()
        upgrade_6_0_to_6_1_plugins_cluster_attrs_use_ids_mapping(connection)
        plugin_attr = self.cluster.attributes.editable['some_plugin_name']
        self.assertIsNone(plugin_attr['metadata']['plugin_id'])
        self.assertNotIn('plugin_version', plugin_attr['metadata'])
