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

import glob
import os
from urlparse import urljoin

import yaml

from nailgun.logger import logger
from nailgun.settings import settings


class ClusterAttributesPlugin(object):
    """Implements wrapper for plugin db model to provide
    logic related to configuration files.
    1. Uploading plugin provided cluster attributes
    2. Uploading tasks
    3. Enabling/Disabling of plugin based on cluster attributes
    4. Providing repositories/deployment scripts related info to clients
    """

    environment_config_name = 'environment_config.yaml'
    task_config_name = 'tasks.yaml'

    def __init__(self, plugin):
        self.plugin = plugin
        self.plugin_path = os.path.join(
            settings.PLUGINS_PATH,
            self.full_name)
        self.config_file = os.path.join(
            self.plugin_path,
            self.environment_config_name)
        self.tasks = []

    def _load_config(self, config):
        if os.access(config, os.R_OK):
            with open(config, "r") as conf:
                return yaml.load(conf.read())
        else:
            logger.warning("Config {0} is not readable.".format(config))

    def get_plugin_attributes(self, cluster):
        """Should be used for initial configuration uploading to
            custom storage. Will be invoked in 2 cases:
            1. Cluster is created but there was no plugins in system
            on that time, so when plugin is uploaded we need to iterate
            over all clusters and decide if plugin should be applied
            2. Plugins is uploaded before cluster creation, in this case
            we will iterate over all plugins and upload configuration for them

            In this case attributes will be added to same cluster attributes
            model and stored in editable field
        """
        config = {}
        if os.path.exists(self.config_file):
            config = self._load_config(self.config_file)
        if self.validate_cluster_compatibility(cluster):
            attrs = config.get("attributes", {})
            self.update_metadata(attrs)
            return {self.plugin.name: attrs}
        return {}

    def validate_cluster_compatibility(self, cluster):
        """Validates if plugin is compatible with cluster.
        - validates operating systems
        - modes of clusters (simple or ha)
        - release version
        """
        for release in self.plugin.releases:
            os_compat = (cluster.release.operating_system.lower()
                         == release['os'].lower())
            # plugin writer should be able to specify ha in release['mode']
            # and know nothing about ha_compact
            mode_compat = any(mode in cluster.mode for mode in release['mode'])
            release_version_compat = (
                cluster.release.version == release['version'])
            if all((os_compat, mode_compat, release_version_compat)):
                return True
        return False

    def process_cluster_attributes(self, cluster, cluster_attrs):
        """Checks cluster attributes for plugin related metadata.
        Then enable or disable plugin for cluster based on metadata
        enabled field.
        """
        custom_attrs = cluster_attrs.get(self.plugin.name, {})

        if custom_attrs:
            # Skip if it's wrong plugin version
            attr_plugin_version = custom_attrs['metadata']['plugin_version']
            if attr_plugin_version != self.plugin.version:
                return

            enable = custom_attrs['metadata']['enabled']
            # value is true and plugin is not enabled for this cluster
            # that means plugin was enabled on this request
            if enable and cluster not in self.plugin.clusters:
                self.plugin.clusters.append(cluster)
            # value is false and plugin is enabled for this cluster
            # that means plugin was disabled on this request
            elif not enable and cluster in self.plugin.clusters:
                self.plugin.clusters.remove(cluster)

    def update_metadata(self, attributes):
        """Overwrights only default values in metadata.
        Plugin should be able to provide UI "native" conditions
        to enable/disable plugin on UI itself
        """
        attributes.setdefault('metadata', {})
        attributes['metadata'].update(self.default_metadata)
        return attributes

    @property
    def default_metadata(self):
        return {u'enabled': False, u'toggleable': True,
                u'weight': 70, u'label': self.plugin.title,
                'plugin_version': self.plugin.version}

    def set_cluster_tasks(self, cluster):
        """Loads plugins provided tasks from tasks config file and
        sets them to instance tasks variable.
        """
        task_yaml = os.path.join(
            self.plugin_path,
            self.task_config_name)
        if os.path.exists(task_yaml):
            self.tasks = self._load_config(task_yaml)

    def filter_tasks(self, tasks, stage):
        filtered = []
        for task in tasks:
            if stage and stage == task.get('stage'):
                filtered.append(task)
        return filtered

    @property
    def plugin_release_versions(self):
        if not self.plugin.releases:
            return set()
        return set([rel['version'] for rel in self.plugin.releases])

    @property
    def full_name(self):
        return u'{0}-{1}'.format(self.plugin.name, self.plugin.version)

    def get_release_info(self, release):
        """Returns plugin release information which corresponds to
            a provided release.
        """
        os = release.operating_system.lower()
        version = release.version

        release_info = filter(
            lambda r: (r['os'] == os and
                       r['version'] == version),
            self.plugin.releases)

        return release_info[0]

    @property
    def slaves_scripts_path(self):
        return settings.PLUGINS_SLAVES_SCRIPTS_PATH.format(
            plugin_name=self.full_name)

    def repo_files(self, cluster):
        release_info = self.get_release_info(cluster.release)
        repo_path = os.path.join(
            settings.PLUGINS_PATH,
            self.full_name,
            release_info['repository_path'],
            '*')
        return glob.glob(repo_path)

    def repo_url(self, cluster):
        release_info = self.get_release_info(cluster.release)
        repo_base = settings.PLUGINS_REPO_URL.format(
            master_ip=settings.MASTER_IP,
            plugin_name=self.full_name)

        return urljoin(repo_base, release_info['repository_path'])

    def master_scripts_path(self, cluster):
        release_info = self.get_release_info(cluster.release)
        # NOTE(eli): we cannot user urljoin here, because it
        # works wrong in case, if protocol is rsync
        base_url = settings.PLUGINS_SLAVES_RSYNC.format(
            master_ip=settings.MASTER_IP,
            plugin_name=self.full_name)
        return '{0}{1}'.format(
            base_url,
            release_info['deployment_scripts_path'])
