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
from nailgun.test import base
from nailgun.utils import reverse


class TestComponentHandler(base.BaseIntegrationTest):

    def setUp(self):
        super(TestComponentHandler, self).setUp()
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

    def test_get_components(self):
        release_id = self.release.id
        plugin_id = self.plugin.id

        resp = self.app.get(
            reverse(
                'ComponentCollectionHandler',
                kwargs={'release_id': release_id}),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        self.assertEqual(resp.json_body, [
            {
                'name': 'test_component_1',
                'type': 'hypervisor',
                'releases_ids': [release_id],
                'plugin_id': None,
                'compatible': {
                    'hypervisors': '*',
                    'networks': [],
                    'storages': ['object:block:swift'],
                    'additional_services': []}},
            {
                'name': 'test_component_2',
                'type': 'additional_service',
                'releases_ids': [],
                'plugin_id': plugin_id,
                'compatible': {
                    'hypervisors': '*',
                    'networks': [],
                    'storages': ['object:block:swift'],
                    'additional_services': []}}])
