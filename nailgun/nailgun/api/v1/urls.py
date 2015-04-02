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

from nailgun.api.v1.handlers.assignment import NodeAssignmentHandler
from nailgun.api.v1.handlers.assignment import NodeUnassignmentHandler

from nailgun.api.v1.handlers.capacity import CapacityLogCsvHandler
from nailgun.api.v1.handlers.capacity import CapacityLogHandler

from nailgun.api.v1.handlers.cluster import ClusterAttributesDefaultsHandler
from nailgun.api.v1.handlers.cluster import ClusterAttributesHandler
from nailgun.api.v1.handlers.cluster import ClusterChangesHandler
from nailgun.api.v1.handlers.cluster import ClusterCollectionHandler
from nailgun.api.v1.handlers.cluster import ClusterDeploymentTasksHandler
from nailgun.api.v1.handlers.cluster import ClusterGeneratedData
from nailgun.api.v1.handlers.cluster import ClusterHandler
from nailgun.api.v1.handlers.cluster import ClusterReposHandler
from nailgun.api.v1.handlers.cluster import ClusterResetHandler
from nailgun.api.v1.handlers.cluster import ClusterStopDeploymentHandler
from nailgun.api.v1.handlers.cluster import ClusterUpdateHandler
from nailgun.api.v1.handlers.cluster import VmwareAttributesDefaultsHandler
from nailgun.api.v1.handlers.cluster import VmwareAttributesHandler

from nailgun.api.v1.handlers.disks import NodeDefaultsDisksHandler
from nailgun.api.v1.handlers.disks import NodeDisksHandler
from nailgun.api.v1.handlers.disks import NodeVolumesInformationHandler

from nailgun.api.v1.handlers.logs import LogEntryCollectionHandler
from nailgun.api.v1.handlers.logs import LogPackageDefaultConfig
from nailgun.api.v1.handlers.logs import LogPackageHandler
from nailgun.api.v1.handlers.logs import LogSourceByNodeCollectionHandler
from nailgun.api.v1.handlers.logs import LogSourceCollectionHandler
from nailgun.api.v1.handlers.node_group import NodeGroupCollectionHandler
from nailgun.api.v1.handlers.node_group import NodeGroupHandler

from nailgun.api.v1.handlers.network_configuration \
    import NeutronNetworkConfigurationHandler
from nailgun.api.v1.handlers.network_configuration \
    import NeutronNetworkConfigurationVerifyHandler
from nailgun.api.v1.handlers.network_configuration \
    import NovaNetworkConfigurationHandler
from nailgun.api.v1.handlers.network_configuration \
    import NovaNetworkConfigurationVerifyHandler

from nailgun.api.v1.handlers.node import NodeAgentHandler
from nailgun.api.v1.handlers.node import NodeCollectionHandler
from nailgun.api.v1.handlers.node import NodeHandler
from nailgun.api.v1.handlers.node import NodesAllocationStatsHandler

from nailgun.api.v1.handlers.plugin import PluginCollectionHandler
from nailgun.api.v1.handlers.plugin import PluginHandler

from nailgun.api.v1.handlers.node import NodeCollectionNICsDefaultHandler
from nailgun.api.v1.handlers.node import NodeCollectionNICsHandler
from nailgun.api.v1.handlers.node import NodeNICsDefaultHandler
from nailgun.api.v1.handlers.node import NodeNICsHandler

from nailgun.api.v1.handlers.notifications import NotificationCollectionHandler
from nailgun.api.v1.handlers.notifications import NotificationHandler

from nailgun.api.v1.handlers.orchestrator import DefaultDeploymentInfo
from nailgun.api.v1.handlers.orchestrator import DefaultPostPluginsHooksInfo
from nailgun.api.v1.handlers.orchestrator import DefaultPrePluginsHooksInfo
from nailgun.api.v1.handlers.orchestrator import DefaultProvisioningInfo
from nailgun.api.v1.handlers.orchestrator import DeploymentInfo
from nailgun.api.v1.handlers.orchestrator import DeploySelectedNodes
from nailgun.api.v1.handlers.orchestrator import DeploySelectedNodesWithTasks
from nailgun.api.v1.handlers.orchestrator import ProvisioningInfo
from nailgun.api.v1.handlers.orchestrator import ProvisionSelectedNodes
from nailgun.api.v1.handlers.orchestrator import TaskDeployGraph

from nailgun.api.v1.handlers.registration import FuelLoginForm
from nailgun.api.v1.handlers.registration import FuelRegistrationForm
from nailgun.api.v1.handlers.registration import FuelRestorePasswordForm

from nailgun.api.v1.handlers.release import ReleaseCollectionHandler
from nailgun.api.v1.handlers.release import ReleaseDeploymentTasksHandler
from nailgun.api.v1.handlers.release import ReleaseHandler
from nailgun.api.v1.handlers.release import ReleaseNetworksHandler

from nailgun.api.v1.handlers.role import RoleCollectionHandler
from nailgun.api.v1.handlers.role import RoleHandler

from nailgun.api.v1.handlers.tasks import TaskCollectionHandler
from nailgun.api.v1.handlers.tasks import TaskHandler

from nailgun.api.v1.handlers.version import VersionHandler

from nailgun.api.v1.handlers.removed import RemovedIn51RedHatAccountHandler
from nailgun.api.v1.handlers.removed import RemovedIn51RedHatSetupHandler

from nailgun.api.v1.handlers.master_node_settings \
    import MasterNodeSettingsHandler

urls = (
    r'/releases/?$',
    ReleaseCollectionHandler,
    r'/releases/(?P<obj_id>\d+)/?$',
    ReleaseHandler,
    r'/releases/(?P<obj_id>\d+)/networks/?$',
    ReleaseNetworksHandler,
    r'/releases/(?P<obj_id>\d+)/deployment_tasks/?$',
    ReleaseDeploymentTasksHandler,

    r'/releases/(?P<release_id>\d+)/roles/?$',
    RoleCollectionHandler,
    r'/releases/(?P<release_id>\d+)/roles/(?P<role_name>[a-zA-Z-_]+)/?$',
    RoleHandler,

    r'/clusters/?$',
    ClusterCollectionHandler,
    r'/clusters/(?P<obj_id>\d+)/?$',
    ClusterHandler,
    r'/clusters/(?P<cluster_id>\d+)/changes/?$',
    ClusterChangesHandler,
    r'/clusters/(?P<cluster_id>\d+)/attributes/?$',
    ClusterAttributesHandler,
    r'/clusters/(?P<cluster_id>\d+)/attributes/defaults/?$',
    ClusterAttributesDefaultsHandler,
    r'/clusters/(?P<cluster_id>\d+)/attributes/repos/?$',
    ClusterReposHandler,

    # nova network-related
    r'/clusters/(?P<cluster_id>\d+)/network_configuration/nova_network/?$',
    NovaNetworkConfigurationHandler,
    r'/clusters/(?P<cluster_id>\d+)/network_configuration/'
    'nova_network/verify/?$',
    NovaNetworkConfigurationVerifyHandler,
    # neutron-related
    r'/clusters/(?P<cluster_id>\d+)/network_configuration/neutron/?$',
    NeutronNetworkConfigurationHandler,
    r'/clusters/(?P<cluster_id>\d+)/network_configuration/'
    'neutron/verify/?$',
    NeutronNetworkConfigurationVerifyHandler,

    r'/clusters/(?P<cluster_id>\d+)/orchestrator/deployment/?$',
    DeploymentInfo,
    r'/clusters/(?P<cluster_id>\d+)/orchestrator/deployment/defaults/?$',
    DefaultDeploymentInfo,
    r'/clusters/(?P<cluster_id>\d+)/orchestrator/provisioning/?$',
    ProvisioningInfo,
    r'/clusters/(?P<cluster_id>\d+)/orchestrator/provisioning/defaults/?$',
    DefaultProvisioningInfo,
    r'/clusters/(?P<cluster_id>\d+)/generated/?$',
    ClusterGeneratedData,
    r'/clusters/(?P<cluster_id>\d+)/orchestrator/plugins_pre_hooks/?$',
    DefaultPrePluginsHooksInfo,
    r'/clusters/(?P<cluster_id>\d+)/orchestrator/plugins_post_hooks/?$',
    DefaultPostPluginsHooksInfo,

    r'/clusters/(?P<cluster_id>\d+)/provision/?$',
    ProvisionSelectedNodes,
    r'/clusters/(?P<cluster_id>\d+)/deploy/?$',
    DeploySelectedNodes,
    r'/clusters/(?P<cluster_id>\d+)/deploy_tasks/?$',
    DeploySelectedNodesWithTasks,
    r'/clusters/(?P<cluster_id>\d+)/deploy_tasks/graph.gv$',
    TaskDeployGraph,
    r'/clusters/(?P<cluster_id>\d+)/stop_deployment/?$',
    ClusterStopDeploymentHandler,
    r'/clusters/(?P<cluster_id>\d+)/reset/?$',
    ClusterResetHandler,
    r'/clusters/(?P<cluster_id>\d+)/update/?$',
    ClusterUpdateHandler,
    r'/clusters/(?P<obj_id>\d+)/deployment_tasks/?$',
    ClusterDeploymentTasksHandler,


    r'/clusters/(?P<cluster_id>\d+)/assignment/?$',
    NodeAssignmentHandler,
    r'/clusters/(?P<cluster_id>\d+)/unassignment/?$',
    NodeUnassignmentHandler,

    r'/clusters/(?P<cluster_id>\d+)/vmware_attributes/?$',
    VmwareAttributesHandler,
    r'/clusters/(?P<cluster_id>\d+)/vmware_attributes/defaults/?$',
    VmwareAttributesDefaultsHandler,

    r'/nodegroups/?$',
    NodeGroupCollectionHandler,
    r'/nodegroups/(?P<obj_id>\d+)/?$',
    NodeGroupHandler,

    r'/nodes/?$',
    NodeCollectionHandler,
    r'/nodes/agent/?$',
    NodeAgentHandler,
    r'/nodes/(?P<obj_id>\d+)/?$',
    NodeHandler,
    r'/nodes/(?P<node_id>\d+)/disks/?$',
    NodeDisksHandler,
    r'/nodes/(?P<node_id>\d+)/disks/defaults/?$',
    NodeDefaultsDisksHandler,
    r'/nodes/(?P<node_id>\d+)/volumes/?$',
    NodeVolumesInformationHandler,
    r'/nodes/interfaces/?$',
    NodeCollectionNICsHandler,
    r'/nodes/interfaces/default_assignment/?$',
    NodeCollectionNICsDefaultHandler,
    r'/nodes/(?P<node_id>\d+)/interfaces/?$',
    NodeNICsHandler,
    r'/nodes/(?P<node_id>\d+)/interfaces/default_assignment/?$',
    NodeNICsDefaultHandler,
    r'/nodes/allocation/stats/?$',
    NodesAllocationStatsHandler,
    r'/tasks/?$',
    TaskCollectionHandler,
    r'/tasks/(?P<obj_id>\d+)/?$',
    TaskHandler,

    r'/plugins/(?P<obj_id>\d+)/?$',
    PluginHandler,
    r'/plugins/?$',
    PluginCollectionHandler,

    r'/notifications/?$',
    NotificationCollectionHandler,
    r'/notifications/(?P<obj_id>\d+)/?$',
    NotificationHandler,

    r'/logs/?$',
    LogEntryCollectionHandler,
    r'/logs/package/?$',
    LogPackageHandler,
    r'/logs/package/config/default/?$',
    LogPackageDefaultConfig,
    r'/logs/sources/?$',
    LogSourceCollectionHandler,
    r'/logs/sources/nodes/(?P<node_id>\d+)/?$',
    LogSourceByNodeCollectionHandler,

    r'/tracking/registration/?$',
    FuelRegistrationForm,
    r'/tracking/login/?$',
    FuelLoginForm,
    r'/tracking/restore_password/?$',
    FuelRestorePasswordForm,

    r'/version/?$',
    VersionHandler,

    r'/capacity/?$',
    CapacityLogHandler,
    r'/capacity/csv/?$',
    CapacityLogCsvHandler,

    r'/redhat/account/?$',
    RemovedIn51RedHatAccountHandler,
    r'/redhat/setup/?$',
    RemovedIn51RedHatSetupHandler,

    r'/settings/?$',
    MasterNodeSettingsHandler,
)

urls = [i if isinstance(i, str) else i.__name__ for i in urls]

_locals = locals()


def app():
    return web.application(urls, _locals)


def public_urls():
    return {r'/nodes/?$': ['POST'],
            r'/nodes/agent/?$': ['PUT'],
            r'/version/?$': ['GET'],
            }
