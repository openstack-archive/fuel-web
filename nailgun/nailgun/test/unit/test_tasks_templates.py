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

from nailgun.orchestrator import tasks_templates


class TestMakeTask(base.BaseTestCase):

    def test_make_ubuntu_sources_task(self):
        result = tasks_templates.make_ubuntu_sources_task(
            [1, 2, 3],
            {
                'name': 'plugin_name',
                'type': 'deb',
                'uri': 'http://url',
                'suite': '/',
                'section': '',
                'priority': 1001
            })

        self.assertEqual(
            result,
            {'parameters': {
                'data': 'deb http://url / ',
                'path': '/etc/apt/sources.list.d/plugin_name.list'},
             'type': 'upload_file',
             'uids': [1, 2, 3]})

    def test_make_ubuntu_preferences_task(self):
        result = tasks_templates.make_ubuntu_preferences_task(
            [1, 2, 3],
            {
                'name': 'plugin_name',
                'type': 'deb',
                'uri': 'http://url',
                'suite': '/',
                'section': '',
                'priority': 1001
            })
        self.assertEqual(
            result,
            {'parameters': {
                'data': 'Package: *\nPin: release n=/\nPin-Priority: 1001',
                'path': '/etc/apt/preferences.d/plugin_name'},
             'type': 'upload_file',
             'uids': [1, 2, 3]})

        result = tasks_templates.make_ubuntu_preferences_task(
            [1, 2, 3],
            {
                'name': 'plugin_name',
                'type': 'deb',
                'uri': 'http://url',
                'suite': 'jessie',
                'section': 'main universe',
                'priority': 1004
            })
        self.assertEqual(
            result,
            {'parameters': {
                'data': ('Package: *\n'
                         'Pin: release n=jessie,c=main,c=universe\n'
                         'Pin-Priority: 1004'),
                'path': '/etc/apt/preferences.d/plugin_name'},
             'type': 'upload_file',
             'uids': [1, 2, 3]})

    def test_make_ubuntu_unauth_repos_task(self):
        result = tasks_templates.make_ubuntu_unauth_repos_task([1, 2, 3])
        self.assertEqual(
            result,
            {'parameters': {
                'data': 'APT::Get::AllowUnauthenticated 1;\n',
                'path': '/etc/apt/apt.conf.d/02mirantis-allow-unsigned'},
             'type': 'upload_file',
             'uids': [1, 2, 3]})

    def test_make_centos_repo_task(self):
        result = tasks_templates.make_centos_repo_task(
            [1, 2, 3],
            {
                'name': 'plugin_name',
                'type': 'rpm',
                'uri': 'http://url',
                'priority': 1
            })
        self.assertEqual(
            result,
            {'parameters': {
                'data': ('[plugin_name]\nname=Plugin plugin_name repository\n'
                         'baseurl=http://url\ngpgcheck=0\npriority=1'),
                'path': '/etc/yum.repos.d/plugin_name.repo'},
             'type': 'upload_file',
             'uids': [1, 2, 3]})

    def test_make_reboot_task(self):
        result = tasks_templates.make_reboot_task(
            [1, 2, 3],
            {'parameters': {'timeout': 10}})

        self.assertEqual(
            result,
            {'type': 'reboot',
             'uids': [1, 2, 3],
             'parameters': {
                 'timeout': 10}})
