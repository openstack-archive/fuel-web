from nailgun.extensions import BaseExtension
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
         'handler': NovaNetworkConfigurationVerifyHandler}
    ]

    @classmethod
    def on_node_create(cls, node):
        pass

    @classmethod
    def on_node_update(cls, node):
        pass

    @classmethod
    def on_node_reset(cls, node):
        pass

    @classmethod
    def on_node_delete(cls, node):
        pass

    @classmethod
    def on_node_collection_delete(cls, node_ids):
        pass

    @classmethod
    def on_cluster_delete(cls, cluster):
        pass

    @classmethod
    def on_before_deployment_check(cls, cluster):
        pass
