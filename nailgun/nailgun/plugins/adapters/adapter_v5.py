#    Copyright 2016 Mirantis, Inc.
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

import nailgun
from nailgun.plugins.adapters import PluginAdapterV4
from nailgun.plugins import loaders


class PluginAdapterV5(PluginAdapterV4):
    """Plugin wrapper class for package version 5.0.0."""

    loader_class = loaders.PluginLoaderV5

    @property
    def attributes_processors(self):
        ap = super(PluginAdapterV5, self).attributes_processors
        ap.update({
            'releases': self._process_releases,
            'graphs': self._make_graphs_dict_by_type
        })
        return ap

    def _make_graphs_dict_by_type(self, graphs_list):

        graphs_to_create = {}
        for graph in graphs_list or []:
            self.graphs_to_create[graph.pop('type')] = graph
        return graphs_to_create

    @staticmethod
    def _create_release_from_configuration(configuration):
        """Create templated release and graphs for given configuration.

        :param configuration:
        :return:
        """
        # deployment tasks not supposed for the release description
        # but we fix this developer mistake automatically

        # apply base template
        base_release = configuration.pop('base_release', None)
        if base_release:
            base_release.update(configuration)
            configuration = base_release

        # process graphs
        graphs_by_type = {}
        graphs_list = configuration.pop('graphs', None)
        for graph in graphs_list:
            graphs_by_type[graph['type']] = graph['graph']
        configuration['graphs'] = graphs_by_type
        nailgun.objects.Release.create(configuration)

    def _process_releases(self, releases_records):
        """Split new release records from old-style release-deps records.

        :param releases_records: list of plugins and releases data
        :type releases_records: list

        :return: configurations that are extending existing
        :rtype: list
        """
        extend_releases = []
        for release in releases_records:
            is_basic_release = release.get('is_release', False)
            if is_basic_release:
                self._create_release_from_configuration(release)
            else:
                extend_releases.append(release)

        return extend_releases
