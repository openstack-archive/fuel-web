# -*- coding: utf-8 -*-

#    Copyright 2014 Mirantis, Inc.
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

from nailgun.test import base

from nailgun.orchestrator import plugins_serializers


class TestMakeTask(base.BaseTestCase):

    def test_make_ubuntu_repo_task(self):
        result = plugins_serializers.make_ubuntu_repo_task(
            'plugin_name',
            'http://url',
            [1, 2, 3])

        self.assertEqual(
            result,
            {'parameters': {
                'data': 'deb http://url /',
                'path': '/etc/apt/sources.list.d/plugin_name.list'},
             'type': 'upload_file',
             'uids': [1, 2, 3]})
