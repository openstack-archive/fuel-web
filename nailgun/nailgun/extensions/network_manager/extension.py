#  Licensed under the Apache License, Version 2.0 (the "License"); you may
#  not use this file except in compliance with the License. You may obtain
#  a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#  WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#  License for the specific language governing permissions and limitations
#  under the License.

from .task.manager import UpdateDnsmasqTaskManager
from nailgun import consts
from nailgun import errors
from nailgun.extensions import BaseExtension
from nailgun.extensions.network_manager.handlers.network_configuration import\
    NetworkAttributesDeployedHandler
from nailgun.extensions.network_manager.handlers.network_configuration import\
    NeutronNetworkConfigurationHandler
from nailgun.extensions.network_manager.handlers.network_configuration import\
    NeutronNetworkConfigurationVerifyHandler
from nailgun.extensions.network_manager.handlers.network_configuration import\
    NovaNetworkConfigurationHandler
from nailgun.extensions.network_manager.handlers.network_configuration import\
    NovaNetworkConfigurationVerifyHandler
from nailgun.extensions.network_manager.handlers.network_configuration import\
    TemplateNetworkConfigurationHandler

from nailgun.extensions.network_manager.handlers.network_group import \
    NetworkGroupCollectionHandler
from nailgun.extensions.network_manager.handlers.network_group import \
    NetworkGroupHandler
from nailgun.extensions.network_manager.handlers.vip import \
    ClusterVIPCollectionHandler
from nailgun.extensions.network_manager.handlers.vip import ClusterVIPHandler

from nailgun.extensions.network_manager.handlers.nic import \
    NodeBondAttributesDefaultsHandler
from nailgun.extensions.network_manager.handlers.nic import \
    NodeCollectionNICsDefaultHandler
from nailgun.extensions.network_manager.handlers.nic import \
    NodeCollectionNICsHandler
from nailgun.extensions.network_manager.handlers.nic import \
    NodeNICsDefaultHandler
from nailgun.extensions.network_manager.handlers.nic import \
    NodeNICsHandler

from nailgun import objects


class NetworkManagerExtension(BaseExtension):
    name = 'network_manager'
    version = '1.0.0'
    description = 'Network Manager'

    data_pipelines = []
    urls = [
        {'uri': r'/clusters/(?P<cluster_id>\d+)/network_configuration'
                r'/ips/vips/?$',
         'handler': ClusterVIPCollectionHandler},
        {'uri': r'/clusters/(?P<cluster_id>\d+)/network_configuration'
                r'/ips/(?P<ip_addr_id>\d+)/vips/?$',
         'handler': ClusterVIPHandler},
        {'uri': r'/networks/?$',
         'handler': NetworkGroupCollectionHandler},
        {'uri': r'/networks/(?P<obj_id>\d+)/?$',
         'handler': NetworkGroupHandler},
        {'uri': r'/clusters/(?P<cluster_id>\d+)/network_configuration/'
                r'neutron/?$',
         'handler': NeutronNetworkConfigurationHandler},
        {'uri': r'/clusters/(?P<cluster_id>\d+)/network_configuration/'
                r'neutron/verify/?$',
         'handler': NeutronNetworkConfigurationVerifyHandler},
        {'uri': r'/clusters/(?P<cluster_id>\d+)/network_configuration/'
                r'template/?$',
         'handler': TemplateNetworkConfigurationHandler},
        {'uri': r'/clusters/(?P<cluster_id>\d+)/network_configuration/'
                r'nova_network/?$',
         'handler': NovaNetworkConfigurationHandler},
        {'uri': r'/clusters/(?P<cluster_id>\d+)/network_configuration/'
                r'nova_network/verify/?$',
         'handler': NovaNetworkConfigurationVerifyHandler},
        {'uri': r'/nodes/(?P<node_id>\d+)/bonds/attributes/defaults/?$',
         'handler': NodeBondAttributesDefaultsHandler},
        {'uri': r'/nodes/interfaces/?$',
         'handler': NodeCollectionNICsHandler},
        {'uri': r'/nodes/interfaces/default_assignment/?$',
         'handler': NodeCollectionNICsDefaultHandler},
        {'uri': r'/nodes/(?P<node_id>\d+)/interfaces/?$',
         'handler': NodeNICsHandler},
        {'uri': r'/nodes/(?P<node_id>\d+)/interfaces/default_assignment/?$',
         'handler': NodeNICsDefaultHandler},
        {'uri': r'/clusters/(?P<cluster_id>\d+)/network_configuration/'
                r'deployed?$',
         'handler': NetworkAttributesDeployedHandler}
    ]

    @classmethod
    def on_cluster_create(cls, cluster, data):
        try:
            net_manager = objects.Cluster.get_network_manager(cluster)
            net_manager.create_network_groups_and_config(cluster, data)
            objects.Cluster.add_pending_changes(
                cluster, consts.CLUSTER_CHANGES.networks)
            net_manager.assign_vips_for_net_groups(cluster)
        except (
            errors.OutOfVLANs,
            errors.OutOfIPs,
            errors.NoSuitableCIDR,

            # VIP assignment related errors
            errors.CanNotFindCommonNodeGroup,
            errors.CanNotFindNetworkForNodeGroup,
            errors.DuplicatedVIPNames
        ) as exc:
            raise errors.CannotCreate(exc.message)

    @classmethod
    def on_cluster_patch_attributes(cls, cluster, public_map):

        roles_metadata = objects.Cluster.get_roles(cluster)
        nm = objects.Cluster.get_network_manager(cluster)
        nm.update_restricted_networks(cluster)
        objects.NetworkGroup._update_public_network(
            cluster, public_map, roles_metadata
        )

    @classmethod
    def after_cluster_delete(cls, cluster):
        if len(cluster.node_groups) > 1:
            UpdateDnsmasqTaskManager().execute()

    @classmethod
    def on_nodegroup_create(cls, ng):
        try:
            cluster = objects.Cluster.get_by_uid(ng.cluster_id)
            nm = objects.Cluster.get_network_manager(cluster)
            nst = cluster.network_config.segmentation_type
            # We have two node groups here when user adds the first custom
            # node group.
            if (objects.NodeGroupCollection.get_by_cluster_id(cluster.id)
                    .count() == 2):
                nm.ensure_gateways_present_in_default_node_group(cluster)
            nm.create_network_groups(
                cluster, neutron_segment_type=nst, node_group_id=ng.id,
                set_all_gateways=True)
            nm.create_admin_network_group(ng.cluster_id, ng.id)
        except (
            errors.OutOfVLANs,
            errors.OutOfIPs,
            errors.NoSuitableCIDR
        ) as exc:
            raise errors.CannotCreate(exc.message)

    @classmethod
    def on_before_deployment_serialization(cls, cluster, nodes,
                                           ignore_customized):
        # TODO(apply only for specified subset of nodes)
        nm = objects.Cluster.get_network_manager(cluster)
        nm.prepare_for_deployment(
            cluster, cluster.nodes if nodes is None else nodes
        )

    @classmethod
    def on_before_provisioning_serialization(cls, cluster, nodes,
                                             ignore_customized):
        nm = objects.Cluster.get_network_manager(cluster)
        nm.prepare_for_provisioning(
            cluster.nodes if nodes is None else nodes
        )

    @classmethod
    def on_node_reset(cls, node):
        objects.IPAddr.delete_by_node(node.id)

    @classmethod
    def on_remove_node_from_cluster(cls, node):
        netmanager = objects.Cluster.get_network_manager(node.cluster)
        netmanager.clear_assigned_networks(node)
        netmanager.clear_bond_configuration(node)

    @classmethod
    def on_nodegroup_delete(cls, ng):
        netmanager = objects.Cluster.get_network_manager(ng.cluster)
        default_admin_net = objects.NetworkGroup.get_default_admin_network()
        for node in ng.nodes:
            objects.Node.remove_from_cluster(node)
            if not netmanager.is_same_network(node.ip, default_admin_net.cidr):
                objects.Node.set_error_status_and_file_notification(
                    node,
                    consts.NODE_ERRORS.discover,
                    "Node '{0}' nodegroup was deleted which means that it may "
                    "not be able to boot correctly unless it is a member of "
                    "another node group admin network".format(node.hostname)
                )
        try:
            task = UpdateDnsmasqTaskManager().execute()
        except errors.TaskAlreadyRunning:
            raise errors.TaskAlreadyRunning(
                errors.UpdateDnsmasqTaskIsRunning.message
            )
        if task.status == consts.TASK_STATUSES.error:
            raise ValueError(task.message)
