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

from nailgun import consts
from nailgun.objects import ComponentCollection
from nailgun.test import base


class setUpComponentsMixin(object):

    def setup_components(self):
        self.release = self.env.create_release(
            version='2015.1-8.0',
            operating_system='Ubuntu',
            modes=[consts.CLUSTER_MODES.ha_compact])
        self.plugin = self.env.create_plugin(
            name='compatible_plugin',
            fuel_version=['8.0'],
            releases=[{
                'repository_path': 'repositories/ubuntu',
                'version': '2015.1-8.0',
                'os': 'ubuntu',
                'mode': ['ha'],
                'deployment_scripts_path': 'deployment_scripts/'}])
        self.core_component = self.env.create_component(
            release=self.release,
            name='test_component_1')
        self.plugin_component = self.env.create_component(
            plugin=self.plugin,
            name='test_component_2',
            type='additional_service')


class TestComponentCollection(base.BaseTestCase, setUpComponentsMixin):

    def setUp(self):
        super(TestComponentCollection, self).setUp()
        self.setup_components()

    def test_get_all_by_release(self):
        self.incompatible_plugin = self.env.create_plugin()
        self.env.create_component(
            plugin=self.incompatible_plugin,
            name='incompatible_component')
        components = ComponentCollection.get_all_by_release(self.release.id)
        for component in components:
            self.assertIn(
                component.name, ['test_component_1', 'test_component_2'])
            self.assertNotIn(component.name, ['incompatible_component'])
        self.assertEqual(len(components), 2)


class TestComponentSerializer(base.BaseTestCase, setUpComponentsMixin):

    def setUp(self):
        super(TestComponentSerializer, self).setUp()
        self.setup_components()

    def test_component_serialization(self):
        pass
