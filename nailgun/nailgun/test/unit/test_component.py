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
from nailgun.objects.serializers import ComponentSerializer
from nailgun.test import base


class BaseComponentTestCase(base.BaseTestCase):

    def setUp(self):
        super(BaseComponentTestCase, self).setUp()
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


class TestComponentCollection(BaseComponentTestCase):

    def test_get_all_by_release(self):
        self.incompatible_plugin = self.env.create_plugin(
            fuel_version=['6.0'],
            releases=[{
                'repository_path': 'repositories/centos',
                'version': '2014.2-6.0',
                'os': 'centos',
                'mode': ['ha'],
                'deployment_scripts_path': 'deployment_scripts/'}]
        )
        self.incompatible_release = self.env.create_release(
            operating_system='Ubuntu',
            modes=[consts.CLUSTER_MODES.ha_compact])
        self.env.create_component(
            plugin=self.incompatible_plugin,
            name='incompatible_plugin_component')
        self.env.create_component(
            release=self.incompatible_release,
            name='incompatible_core_component')
        components = ComponentCollection.get_all_by_release(self.release.id)
        for component in components:
            self.assertIn(
                component.name, ['test_component_1', 'test_component_2'])
            self.assertNotIn(component.name, [
                'incompatible_plugin_component',
                'incompatible_core_component'])
        self.assertEqual(len(components), 2)


class TestComponentSerializer(BaseComponentTestCase):

    def test_core_component_serialization(self):
        release_id = self.release.id
        component_data = ComponentSerializer.serialize(
            self.core_component)
        self.assertDictEqual(component_data, {
            'name': 'test_component_1',
            'type': 'hypervisor',
            'compatible': {
                'additional_services': [],
                'networks': [],
                'storages': ['object:block:swift'],
                'hypervisors': '*'
            },
            'plugin_id': None,
            'releases_ids': [release_id]})

    def test_plugin_component_serialization(self):
        plugin_id = self.plugin.id
        component_data = ComponentSerializer.serialize(
            self.plugin_component)
        self.assertDictEqual(component_data, {
            'name': 'test_component_2',
            'type': 'additional_service',
            'compatible': {
                'additional_services': [],
                'networks': [],
                'storages': ['object:block:swift'],
                'hypervisors': '*'
            },
            'plugin_id': plugin_id,
            'releases_ids': []})
