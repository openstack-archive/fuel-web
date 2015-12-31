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

from copy import deepcopy
from nailgun import consts
from nailgun.test import base
from nailgun.utils import reverse


class TestComponentHandler(base.BaseIntegrationTest):

    def setUp(self):
        super(TestComponentHandler, self).setUp()
        self.release = self.env.create_release(
            version='2015.1-8.0',
            operating_system='Ubuntu',
            modes=[consts.CLUSTER_MODES.ha_compact],
            components_metadata=self.env.get_default_components(
                name='hypervisor:test_component_1',
                bind='some_action_to_process'))
        self.plugin = self.env.create_plugin(
            name='compatible_plugin',
            fuel_version=['8.0'],
            releases=[{
                'repository_path': 'repositories/ubuntu',
                'version': '2015.1-8.0',
                'os': 'ubuntu',
                'mode': ['ha'],
                'deployment_scripts_path': 'deployment_scripts/'}],
            components_metadata=self.env.get_default_components(
                name='storage:test_component_2',
                bind='some_action_to_process'))

    def test_get_components(self):
        original_components = deepcopy(self.release.components_metadata)
        resp = self.app.get(
            reverse(
                'ComponentCollectionHandler',
                kwargs={'release_id': self.release.id}),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        self.assertEqual(resp.json_body, [
            {
                'name': 'hypervisor:test_component_1',
                'compatible': [
                    {'name': 'hypervisors:*'},
                    {'name': 'storages:object:block:swift'}],
                'incompatible': [
                    {'name': 'networks:*'},
                    {'name': 'additional_services:*'}]},
            {
                'name': 'storage:test_component_2',
                'compatible': [
                    {'name': 'hypervisors:*'},
                    {'name': 'storages:object:block:swift'}],
                'incompatible': [
                    {'name': 'networks:*'},
                    {'name': 'additional_services:*'}]}])
        self.assertItemsEqual(self.release.components_metadata,
                              original_components)

    def test_404_for_get_components_with_none_release_id(self):
        resp = self.app.get(
            reverse(
                'ComponentCollectionHandler',
                kwargs={'release_id': None}),
            headers=self.default_headers,
            expect_errors=True
        )

        self.assertEqual(404, resp.status_code)

    def test_post_components_not_allowed(self):
        resp = self.app.post(
            reverse(
                'ComponentCollectionHandler',
                kwargs={'release_id': self.release.id}),
            headers=self.default_headers,
            expect_errors=True
        )

        self.assertEqual(405, resp.status_code)
