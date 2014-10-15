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


import os

import mock
import yaml

from nailgun.db import db
from nailgun.objects import Plugin
from nailgun.plugins import attr_plugin
from nailgun.settings import settings
from nailgun.test import base


SAMPLE_PLUGIN = {
    'version': '0.1.0',
    'name': 'lbaas_simple',
    'package_version': '1',
    'description': 'Enable to use plugin X for Neutron',
    'types': ['nailgun', 'repository', 'deployment_scripts'],
    'fuel_version': 6.0,
    'releases': [
        {'repository_path': 'repositories/ubuntu',
         'version': '2014.2-6.0', 'os': 'ubuntu',
         'mode': ['ha', 'multinode'],
         'deployment_scripts_path': 'deployment_scripts/'},
        {'repository_path': 'repositories/centos',
         'version': '2014.2-6.0', 'os': 'centos',
         'mode': ['ha', 'multinode'],
         'deployment_scripts_path': 'deployment_scripts/'}]}

ENVIRONMENT_CONFIG = {
    'attributes': {
        'lbaas_simple_text': {
            'value': 'Set default value',
            'type': 'text',
            'description': 'Description for text field',
            'weight': 25,
            'label': 'Text field'}}}


def get_config(*args):
    return mock.mock_open(read_data=yaml.dump(ENVIRONMENT_CONFIG))()


class TestPlugin(base.BaseTestCase):

    def setUp(self):
        super(TestPlugin, self).setUp()
        self.plugin = Plugin.create(SAMPLE_PLUGIN)
        self.env.create(
            release_kwargs={'version': '2014.2-6.0',
                            'operating_system': 'Ubuntu'})
        self.cluster = self.env.clusters[0]
        self.attr_plugin = attr_plugin.ClusterAttributesPlugin(self.plugin)
        db().flush()

    def test_upload_plugin_attributes(self):
        """Should load attributes from environment_config.
        Attributes should contain provided attributes by plugin and
        also generated metadata
        """
        with mock.patch('__builtin__.open') as f_m:
            f_m.side_effect = get_config
            attributes = self.attr_plugin.upload_plugin_attributes(
                self.cluster)
        self.assertEqual(
            attributes['lbaas_simple']['lbaas_simple_text'],
            ENVIRONMENT_CONFIG['attributes']['lbaas_simple_text'])
        self.assertEqual(
            attributes['lbaas_simple']['metadata'],
            self.attr_plugin.metadata['metadata'])

    def test_plugin_release_versions(self):
        """Helper should return set of all release versions this plugin
           is applicable to.
        """
        self.assertEqual(self.attr_plugin.plugin_versions, set(['2014.2-6.0']))

    def test_full_name(self):
        """Plugin full name should be made from name and version."""
        self.assertEqual(
            self.attr_plugin.full_name,
            '{0}-{1}'.format(self.plugin.name, self.plugin.version))

    def test_get_release_info(self):
        """Should return 1st plugin release info which matches
           provided release.
        """
        release = self.attr_plugin.get_release_info(self.cluster.release)
        self.assertEqual(release, SAMPLE_PLUGIN['releases'][0])

    def test_slaves_scripts_path(self):
        expected = settings.PLUGINS_SLAVES_SCRIPTS_PATH.format(
            plugin_name=self.attr_plugin.full_name)
        self.assertEqual(expected, self.attr_plugin.slaves_scripts_path)

    @mock.patch('nailgun.plugins.attr_plugin.glob')
    def test_is_repo_files(self, glob_mock):
        self.attr_plugin.is_repo_files(self.cluster)
        expected_call = os.path.join(
            settings.PLUGINS_PATH,
            self.attr_plugin.full_name,
            'repositories/ubuntu',
            '*')
        glob_mock.glob.assert_called_once_with(expected_call)

    @mock.patch('nailgun.plugins.attr_plugin.urljoin')
    def test_repo_url(self, murljoin):
        self.attr_plugin.repo_url(self.cluster)
        repo_base = settings.PLUGINS_REPO_URL.format(
            master_ip=settings.MASTER_IP,
            plugin_name=self.attr_plugin.full_name)
        murljoin.assert_called_once_with(repo_base, 'repositories/ubuntu')

    def test_master_scripts_path(self):
        base_url = settings.PLUGINS_SLAVES_RSYNC.format(
            master_ip=settings.MASTER_IP,
            plugin_name=self.attr_plugin.full_name)
        expected = '{0}{1}'.format(base_url, 'deployment_scripts/')
        self.assertEqual(
            expected, self.attr_plugin.master_scripts_path(self.cluster))
