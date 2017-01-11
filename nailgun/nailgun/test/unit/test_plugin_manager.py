# -*- coding: utf-8 -*-

#    Copyright 2017 Mirantis, Inc.
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

from nailgun import objects
from nailgun.plugins import manager

from nailgun.test.base import BaseTestCase


class TestPluginManager(BaseTestCase):

    def setUp(self):
        super(TestPluginManager, self).setUp()
        self.cluster = self.env.create()
        self.plugin_manager = manager.PluginManager
        self.plugin = self.env.create_plugin(api=False)

    def test_return_false_if_plugin_used(self):
        self.cluster.plugins.append(self.plugin)
        objects.ClusterPlugin.set_attributes(self.cluster.id,
                                             self.plugin.id,
                                             enabled=True)
        self.db.refresh(self.plugin)
        self.assertEqual(False, self.plugin_manager
                         ._is_plugin_deletable(self.plugin))

    def test_return_true_if_plugin_unused(self):
        self.assertEqual(True, self.plugin_manager
                         ._is_plugin_deletable(self.plugin))
