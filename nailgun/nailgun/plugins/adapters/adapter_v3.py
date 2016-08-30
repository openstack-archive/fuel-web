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
from nailgun import consts
from nailgun.plugins.adapters import PluginAdapterV2
from nailgun.plugins import loaders


class PluginAdapterV3(PluginAdapterV2):
    """Plugin wrapper class for package version 3.0.0."""

    loader_class = loaders.PluginLoaderV3

    def _process_deployment_tasks(self, deployment_tasks):
        dg = nailgun.objects.DeploymentGraph.get_for_model(
            self.plugin, graph_type=consts.DEFAULT_DEPLOYMENT_GRAPH_TYPE)
        if dg:
            nailgun.objects.DeploymentGraph.update(
                dg, {'tasks': deployment_tasks})
        else:
            nailgun.objects.DeploymentGraph.create_for_model(
                {'tasks': deployment_tasks}, self.plugin)
        return deployment_tasks

    @property
    def attributes_processors(self):
        ap = super(PluginAdapterV3, self).attributes_processors
        ap.update({
            'deployment_tasks': self._process_deployment_tasks
        })
        return ap
