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


class TestPlugin(base.BaseTestCase):

    def setUp(self):
        super(TestPlugin, self).setUp()
        self.plugin_metadata = self.env.get_default_plugin_metadata()
        self.plugin = Plugin.create(self.plugin_metadata)
        self.env.create(
            cluster_kwargs={'mode': 'multinode'},
            release_kwargs={
                'version': '2014.2-6.0',
                'operating_system': 'Ubuntu',
                'orchestrator_data': self.env.get_default_orchestrator_data()})
        self.cluster = self.env.clusters[0]
        self.attr_plugin = attr_plugin.ClusterAttributesPlugin(self.plugin)
        self.env_config = self.env.get_default_plugin_env_config()
        self.get_config = lambda *args: mock.mock_open(
            read_data=yaml.dump(self.env_config))()

        db().flush()

    @mock.patch('nailgun.plugins.attr_plugin.open', create=True)
    @mock.patch('nailgun.plugins.attr_plugin.os.access')
    @mock.patch('nailgun.plugins.attr_plugin.os.path.exists')
    def test_get_plugin_attributes(self, mexists, maccess, mopen):
        """Should load attributes from environment_config.
        Attributes should contain provided attributes by plugin and
        also generated metadata
        """
        maccess.return_value = True
        mexists.return_value = True
        mopen.side_effect = self.get_config
        attributes = self.attr_plugin.get_plugin_attributes(self.cluster)
        self.assertEqual(
            attributes['testing_plugin']['plugin_name_text'],
            self.env_config['attributes']['plugin_name_text'])
        self.assertEqual(
            attributes['testing_plugin']['metadata'],
            self.attr_plugin.default_metadata)

    def test_plugin_release_versions(self):
        """Helper should return set of all release versions this plugin
           is applicable to.
        """
        self.assertEqual(
            self.attr_plugin.plugin_release_versions, set(['2014.2-6.0']))

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
        self.assertEqual(release, self.plugin_metadata['releases'][0])

    def test_slaves_scripts_path(self):
        expected = settings.PLUGINS_SLAVES_SCRIPTS_PATH.format(
            plugin_name=self.attr_plugin.full_name)
        self.assertEqual(expected, self.attr_plugin.slaves_scripts_path)

    @mock.patch('nailgun.plugins.attr_plugin.glob')
    def test_repo_files(self, glob_mock):
        self.attr_plugin.repo_files(self.cluster)
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


class TestClusterCompatiblityValidation(base.BaseTestCase):

    def setUp(self):
        super(TestClusterCompatiblityValidation, self).setUp()
        self.plugin = Plugin.create(self.env.get_default_plugin_metadata())
        self.attr_plugin = attr_plugin.ClusterAttributesPlugin(self.plugin)

    def get_cluster(self, os, mode, version):
        release = mock.Mock(operating_system=os, version=version)
        cluster = mock.Mock(mode=mode, release=release)
        return cluster

    def test_validation_ubuntu_ha(self):
        cluster = self.get_cluster(
            os='Ubuntu',
            mode='ha_compact',
            version='2014.2-6.0')
        validated = self.attr_plugin.validate_cluster_compatibility(cluster)
        self.assertTrue(validated)

    def test_validation_centos_multinode(self):
        cluster = self.get_cluster(
            os='Centos',
            mode='multinode',
            version='2014.2-6.0')
        validated = self.attr_plugin.validate_cluster_compatibility(cluster)
        self.assertTrue(validated)

    def test_not_existent_os(self):
        cluster = self.get_cluster(
            os='Fedora',
            mode='multinode',
            version='2014.2-6.0')
        validated = self.attr_plugin.validate_cluster_compatibility(cluster)
        self.assertFalse(validated)

    def test_plugin_provided_ha_compact(self):
        cluster = self.get_cluster(
            os='Ubuntu',
            mode='ha_compact',
            version='2014.2-6.0')
        validated = self.attr_plugin.validate_cluster_compatibility(cluster)
        self.assertTrue(validated)

    def test_version_mismatch(self):
        cluster = self.get_cluster(
            os='Ubuntu',
            mode='ha_compact',
            version='2014.2.1-6.0')
        validated = self.attr_plugin.validate_cluster_compatibility(cluster)
        self.assertFalse(validated)
