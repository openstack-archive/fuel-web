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

import re

import mock
import requests

from oslo_serialization import jsonutils

from nailgun.consts import IRONIC_BOOTSTRAP_PKGS

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

    def test_make_ubuntu_apt_disable_ipv6(self):
        result = tasks_templates.make_ubuntu_apt_disable_ipv6([1, 2, 3])
        self.assertEqual(
            result,
            {'parameters': {
                'data': 'Acquire::ForceIPv4 "true";\n',
                'path': '/etc/apt/apt.conf.d/05disable-ipv6'},
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

    def test_make_centos_repo_task_w_priority(self):
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

    def test_make_centos_repo_task_wo_priority(self):
        result = tasks_templates.make_centos_repo_task(
            [1, 2, 3],
            {
                'name': 'plugin_name',
                'type': 'rpm',
                'uri': 'http://url',
            })
        self.assertEqual(
            result,
            {'parameters': {
                'data': ('[plugin_name]\nname=Plugin plugin_name repository\n'
                         'baseurl=http://url\ngpgcheck=0'),
                'path': '/etc/yum.repos.d/plugin_name.repo'},
             'type': 'upload_file',
             'uids': [1, 2, 3]})

    def test_make_reboot_task(self):
        result = tasks_templates.make_reboot_task(
            [1, 2, 3],
            {'id': 'reboot', 'parameters': {'timeout': 10}})

        self.assertEqual(
            result,
            {'id': 'reboot',
             'type': 'reboot',
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
                }},
            cid=123)

        fuel_image_conf = {
            "image_data": {
                "/mount": {
                    "uri": "http://uri",
                    "format": "ext4"
                }
            },
            "output": "/var/www/nailgun/targetimages",
            "repos": [
                {
                    "name": "repo",
                    "uri": "http://some"
                }
            ],
            "codename": "trusty"
        }

        self.assertEqual(result["type"], "shell")
        self.assertEqual(result["uids"], [1, 2, 3])
        params = result["parameters"].copy()
        del params["cmd"]
        self.assertEqual(
            params,
            {
                'timeout': settings.PROVISIONING_IMAGES_BUILD_TIMEOUT,
                'retries': 1,
                'interval': 1,
                'cwd': '/',
            }
        )
        cmd = result["parameters"]["cmd"].lstrip(
            "fa_build_image --image_build_dir /var/lib/fuel/ibp "
            "--log-file /var/log/fuel-agent-env-123.log "
            "--data_driver nailgun_build_image --input_data '").rstrip("'")
        self.assertEqual(jsonutils.loads(cmd), fuel_image_conf)

    def test_generate_ironic_bootstrap_keys_task(self):
        result = tasks_templates.generate_ironic_bootstrap_keys_task(
            [1, 2, 3],
            cid=123)
        cmd_path = "/etc/puppet/modules/osnailyfacter/modular/astute/"
        self.assertEqual(result, {
            'id': None,
            'type': 'shell',
            'uids': [1, 2, 3],
            'parameters': {
                'cmd': (
                    "sh {cmd_path}generate_keys.sh "
                    "-i 123 "
                    "-s 'ironic' "
                    "-p /var/lib/fuel/keys/ ").format(
                        cmd_path=cmd_path),
                'timeout': 180,
                'retries': 1,
                'interval': 1,
                'cwd': '/'}})

    def test_make_ironic_bootstrap_task(self):
        cid = 123
        bootstrap_path = "/var/www/nailgun/bootstrap/ironic/{cid}".format(
            cid=cid)

        result = tasks_templates.make_ironic_bootstrap_task(
            [1, 2, 3],
            cid=cid)

        extra_conf_files = "/usr/share/ironic-fa-bootstrap-configs/"
        ssh_keys = "/var/lib/fuel/keys/{0}/ironic/ironic.pub".format(cid)

        ironic_bootstrap_pkgs = '--package ' + ' --package '.join(
            IRONIC_BOOTSTRAP_PKGS)

        self.assertEqual(result, {
            'id': None,
            'type': 'shell',
            'uids': [1, 2, 3],
            'parameters': {
                'cmd': (
                    "test -e {bootstrap_path}/* || "
                    "(fuel-bootstrap build {ironic_bootstrap_pkgs} "
                    "--root-ssh-authorized-file {bootstrap_ssh_keys} "
                    "--output-dir {bootstrap_path}/ "
                    "--extra-dir {extra_conf_files} --no-compress "
                    '--no-default-extra-dirs --no-default-packages)').format(
                        cid=cid,
                        extra_conf_files=extra_conf_files,
                        bootstrap_ssh_keys=ssh_keys,
                        ironic_bootstrap_pkgs=ironic_bootstrap_pkgs,
                        bootstrap_path=bootstrap_path),
                'timeout': settings.PROVISIONING_IMAGES_BUILD_TIMEOUT,
                'retries': 1,
                'interval': 1,
                'cwd': '/'}})

    def test_make_download_debian_installer_task(self):
        remote_kernel = ('http://some/a/dists/trusty/main/'
                         'installer-amd64/current/images/'
                         'netboot/ubuntu-installer/amd64/linux')
        remote_initrd = ('http://some/a/dists/trusty/main/'
                         'installer-amd64/current/images/'
                         'netboot/ubuntu-installer/amd64/initrd.gz')

        relative_kernel = ('dists/trusty/main/installer-amd64/current/'
                           'images/netboot/ubuntu-installer/amd64/linux')
        relative_initrd = ('dists/trusty/main/installer-amd64/current/'
                           'images/netboot/ubuntu-installer/amd64/initrd.gz')

        local_kernel = '/var/www/nailgun/ubuntu/x86_64/images/linux'
        local_initrd = '/var/www/nailgun/ubuntu/x86_64/images/initrd.gz'

        # we have to be able to handle both cases with trailing slash
        # and without it
        for uri in ('http://some/a/', 'http://some/a'):
            result = tasks_templates.make_download_debian_installer_task(
                [1, 2, 3],
                repos=[{'name': 'repo', 'uri': uri}],
                installer_kernel={'remote_relative': relative_kernel,
                                  'local': local_kernel},
                installer_initrd={'remote_relative': relative_initrd,
                                  'local': local_initrd})

            self.assertEqual(result, {
                'id': None,
                'type': 'shell',
                'uids': [1, 2, 3],
                'parameters': {
                    'cmd': ('LOCAL_KERNEL_FILE={local_kernel} '
                            'LOCAL_INITRD_FILE={local_initrd} '
                            'download-debian-installer '
                            '{remote_kernel} {remote_initrd}').format(
                                local_kernel=local_kernel,
                                local_initrd=local_initrd,
                                remote_kernel=remote_kernel,
                                remote_initrd=remote_initrd),
                    'timeout': 600,
                    'retries': 1,
                    'interval': 1,
                    'cwd': '/',
                }})


class TestMakeUbuntuPreferencesTask(base.BaseTestCase):

    _fake_debian_release = '''
      Origin: TestOrigin
      Label: TestLabel
      Archive: test-archive
      Codename: testcodename
    '''

    _re_pin = re.compile('Pin: release (.*)')

    def _check_apt_preferences(self, data, sections, priority):
        pins = data.split('\n\n')

        self.assertEqual(len(pins), 1)

        conditions = self._re_pin.search(pins[0]).group(1).split(',')

        # check general template
        self.assertRegexpMatches(
            data, (
                'Package: \*\n'
                'Pin: release .*\n'
                'Pin-Priority: {0}'.format(priority)
            ))

        # check pin
        expected_conditions = [
            'a=test-archive',
            'l=TestLabel',
            'n=testcodename',
            'o=TestOrigin',
        ]
        self.assertItemsEqual(conditions, expected_conditions)

    @mock.patch('nailgun.utils.debian.requests.get',
                return_value=mock.Mock(text=_fake_debian_release))
    def test_make_ubuntu_preferences_task(self, _):
        result = tasks_templates.make_ubuntu_preferences_task(
            [1, 2, 3],
            {
                'name': 'plugin_name',
                'type': 'deb',
                'uri': 'http://url',
                'suite': 'test-archive',
                'section': 'main universe',
                'priority': 1004
            })

        data = result['parameters'].pop('data')
        self.assertEqual(
            result,
            {'parameters': {'path': '/etc/apt/preferences.d/plugin_name.pref'},
             'type': 'upload_file',
             'uids': [1, 2, 3]})

        self._check_apt_preferences(data, ['main', 'universe'], 1004)

    @mock.patch('nailgun.utils.debian.requests.get',
                return_value=mock.Mock(text=_fake_debian_release))
    def test_make_ubuntu_preferences_task_flat(self, _):
        result = tasks_templates.make_ubuntu_preferences_task(
            [1, 2, 3],
            {
                'name': 'plugin_name',
                'type': 'deb',
                'uri': 'http://url',
                'suite': '/',
                'section': '',
                'priority': 1004
            })

        data = result['parameters'].pop('data')
        self.assertEqual(
            result,
            {'parameters': {'path': '/etc/apt/preferences.d/plugin_name.pref'},
             'type': 'upload_file',
             'uids': [1, 2, 3]})

        self._check_apt_preferences(data, [], 1004)

    @mock.patch('nailgun.utils.debian.requests.get')
    def test_make_ubuntu_preferences_task_returns_none_if_errors(self, m_get):
        r = requests.Response()
        r.status_code = 404
        m_get.return_value = r

        result = tasks_templates.make_ubuntu_preferences_task(
            [1, 2, 3],
            {
                'name': 'plugin_name',
                'type': 'deb',
                'uri': 'http://url',
                'suite': 'test-archive',
                'section': 'main universe',
                'priority': 1004
            })

        self.assertIsNone(result)
