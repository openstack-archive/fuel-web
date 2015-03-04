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
from nailgun.settings import settings


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
                'data': 'Package: *\nPin: release a=/\nPin-Priority: 1001',
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

    def test_make_provisioning_images_task(self):
        result = tasks_templates.make_provisioning_images_task(
            [1, 2, 3],
            repos=[
                {'name': 'repo', 'uri': 'http://some'}
            ],
            provision_data={
                'codename': 'trusty',
                'image_data': {
                    '/mount': {
                        'format': 'ext4',
                        'uri': 'http://uri'
                    }
                }})

        self.assertEqual(result, {
            'type': 'shell',
            'uids': [1, 2, 3],
            'parameters': {
                'cmd': ('fuel-image \'{"image_data": {"/mount": {"uri": '
                        '"http://uri", "format": "ext4"}}, "output": '
                        '"/var/www/nailgun/targetimages", "repos": [{"name": '
                        '"repo", "uri": "http://some"}], "codename": '
                        '"trusty"}\''),
                'timeout': settings.PROVISIONING_IMAGES_BUILD_TIMEOUT,
                'cwd': '/',
            }})

    def test_make_download_debian_installer_task(self):
        result = tasks_templates.make_download_debian_installer_task(
            [1, 2, 3],
            repos=[{'name': 'repo', 'uri': 'http://some'}])

        kernel_uri = 'http://some/{0}'.format(
            settings.DEBIAN_INSTALLER_KERNEL_RELATIVE_PATH)
        initrd_uri = 'http://some/{0}'.format(
            settings.DEBIAN_INSTALLER_INITRD_RELATIVE_PATH)

        self.assertEqual(result, {
            'type': 'shell',
            'uids': [1, 2, 3],
            'parameters': {
                'cmd': ('download_debian_installer {0} {1}'.format(
                    kernel_uri, initrd_uri)),
                'timeout': 600,
                'cwd': '/',
            }})
