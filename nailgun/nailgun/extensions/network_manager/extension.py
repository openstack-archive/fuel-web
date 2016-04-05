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

from nailgun.extensions.network_manager.handlers.nic import \
    NodeCollectionNICsDefaultHandler
from nailgun.extensions.network_manager.handlers.nic import \
    NodeCollectionNICsHandler
from nailgun.extensions.network_manager.handlers.nic import \
    NodeNICsDefaultHandler
from nailgun.extensions.network_manager.handlers.nic import \
    NodeNICsHandler


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
        {'uri': r'/nodes/interfaces/?$',
         'handler': NodeCollectionNICsHandler},
        {'uri': r'/nodes/interfaces/default_assignment/?$',
         'handler': NodeCollectionNICsDefaultHandler},
        {'uri': r'/nodes/(?P<node_id>\d+)/interfaces/?$',
         'handler': NodeNICsHandler},
        {'uri': r'/nodes/(?P<node_id>\d+)/interfaces/default_assignment/?$',
         'handler': NodeNICsDefaultHandler}
    ]
