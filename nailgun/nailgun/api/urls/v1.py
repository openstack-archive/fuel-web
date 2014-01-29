# -*- coding: utf-8 -*-

#    Copyright 2013 Mirantis, Inc.
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

import web

from nailgun.api.handlers.capacity import CapacityLogCsvHandler
from nailgun.api.handlers.capacity import CapacityLogHandler

from nailgun.api.handlers.cluster import ClusterAttributesDefaultsHandler
from nailgun.api.handlers.cluster import ClusterAttributesHandler
from nailgun.api.handlers.cluster import ClusterChangesHandler
from nailgun.api.handlers.cluster import ClusterCollectionHandler
from nailgun.api.handlers.cluster import ClusterGeneratedData
from nailgun.api.handlers.cluster import ClusterHandler

from nailgun.api.handlers.disks import NodeDefaultsDisksHandler
from nailgun.api.handlers.disks import NodeDisksHandler
from nailgun.api.handlers.disks import NodeVolumesInformationHandler

from nailgun.api.handlers.logs import LogEntryCollectionHandler
from nailgun.api.handlers.logs import LogPackageHandler
from nailgun.api.handlers.logs import LogSourceByNodeCollectionHandler
from nailgun.api.handlers.logs import LogSourceCollectionHandler

from nailgun.api.handlers.network_configuration \
    import NeutronNetworkConfigurationHandler
from nailgun.api.handlers.network_configuration \
    import NeutronNetworkConfigurationVerifyHandler
from nailgun.api.handlers.network_configuration \
    import NovaNetworkConfigurationHandler
from nailgun.api.handlers.network_configuration \
    import NovaNetworkConfigurationVerifyHandler

from nailgun.api.handlers.node import NodeCollectionHandler
from nailgun.api.handlers.node import NodeHandler
from nailgun.api.handlers.node import NodesAllocationStatsHandler

from nailgun.api.handlers.node import NodeCollectionNICsDefaultHandler
from nailgun.api.handlers.node import NodeCollectionNICsHandler
from nailgun.api.handlers.node import NodeNICsDefaultHandler
from nailgun.api.handlers.node import NodeNICsHandler
from nailgun.api.handlers.node import NodeNICsVerifyHandler

from nailgun.api.handlers.notifications import NotificationCollectionHandler
from nailgun.api.handlers.notifications import NotificationHandler

from nailgun.api.handlers.orchestrator import DefaultDeploymentInfo
from nailgun.api.handlers.orchestrator import DefaultProvisioningInfo
from nailgun.api.handlers.orchestrator import DeploymentInfo
from nailgun.api.handlers.orchestrator import DeploySelectedNodes
from nailgun.api.handlers.orchestrator import ProvisioningInfo
from nailgun.api.handlers.orchestrator import ProvisionSelectedNodes

from nailgun.api.handlers.plugin import PluginCollectionHandler
from nailgun.api.handlers.plugin import PluginHandler

from nailgun.api.handlers.redhat import RedHatAccountHandler
from nailgun.api.handlers.redhat import RedHatSetupHandler
from nailgun.api.handlers.registration import FuelKeyHandler
from nailgun.api.handlers.release import ReleaseCollectionHandler
from nailgun.api.handlers.release import ReleaseHandler

from nailgun.api.handlers.tasks import TaskCollectionHandler
from nailgun.api.handlers.tasks import TaskHandler

from nailgun.api.handlers.version import VersionHandler


_locals = locals()


urls = {
    'releases': {
        '': ReleaseCollectionHandler,
        '(?P<release_id>\d+)': ReleaseHandler,
    },
    'clusters': {
        '': ClusterCollectionHandler,
        r'(?P<cluster_id>\d+)': {
            '': ClusterHandler,
            'changes': ClusterChangesHandler,
            'attributes': ClusterAttributesHandler,
            'attributes/defaults': ClusterAttributesDefaultsHandler,
            'network_configuration': {
                'nova_network': {
                    '': NovaNetworkConfigurationHandler,
                    'verify': NovaNetworkConfigurationVerifyHandler,
                },
                'neutron': {
                    '': NeutronNetworkConfigurationHandler,
                    'verify': NeutronNetworkConfigurationVerifyHandler,
                },
            },
            'orchestrator': {
                'deployment': DeploymentInfo,
                'deployment/defaults': DefaultDeploymentInfo,
                'provisioning': ProvisioningInfo,
                'provisioning/defaults': DefaultProvisioningInfo,
            },
            'generated': ClusterGeneratedData,
            'provision': ProvisionSelectedNodes,
            'deploy': DeploySelectedNodes,
        },
    },
    'nodes': {
        '': NodeCollectionHandler,
        r'(?P<node_id>\d+)': {
            '': NodeHandler,
            'disks': NodeDisksHandler,
            'disks/defaults': NodeDefaultsDisksHandler,
            'volumes': NodeVolumesInformationHandler,
            'interfaces': NodeNICsHandler,
            'interfaces/default_assignment': NodeNICsDefaultHandler,
        },
        'interfaces': NodeCollectionNICsHandler,
        'interfaces/default_assignment': NodeCollectionNICsDefaultHandler,
        'interfaces_verify': NodeNICsVerifyHandler,
        'allocation/stats': NodesAllocationStatsHandler,
    },
    'tasks': {
        '': TaskCollectionHandler,
        '(?P<task_id>\d+)': TaskHandler,
    },
    'notifications': {
        '': NotificationCollectionHandler,
        '(?P<notification_id>\d+)': NotificationHandler,
    },
    'logs': {
        '': LogEntryCollectionHandler,
        'package': LogPackageHandler,
        'sources': LogSourceCollectionHandler,
        r'sources/nodes/(?P<node_id>\d+)': LogSourceByNodeCollectionHandler,
    },
    'registration/key': FuelKeyHandler,
    'version': VersionHandler,
    'plugins': {
        '': PluginCollectionHandler,
        r'(?P<plugin_id>\d+)': PluginHandler,
    },
    'redhat': {
        'account': RedHatAccountHandler,
        'setup': RedHatSetupHandler,
    },
    'capacity': {
        '': CapacityLogHandler,
        'csv': CapacityLogCsvHandler,
    },
}


def deep_walk(mapping):
    for k, v in mapping.iteritems():
        if isinstance(v, dict):
            for child_path, value in deep_walk(v):
                yield (k,) + child_path, value
        else:
            yield (k,) if k else (), v


def preprocess_urls(mapping):
    for path, value in deep_walk(mapping):
        yield '/' + '/'.join(path) + '/?$'
        yield value.__name__


def app():
    return web.application(preprocess_urls(urls), _locals)
