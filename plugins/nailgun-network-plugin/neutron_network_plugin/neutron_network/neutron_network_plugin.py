from nailgun_network.network_plugin import NailgunNetworkPlugin, NeutronNetworkConfigurationHandler, \
    NeutronNetworkConfigurationVerifyHandler


class NeutronNetworkPlugin(NailgunNetworkPlugin):

    __plugin_name__ = "neutron_network_plugin"

    @classmethod
    def get_urls(cls):
        urls = (
            # neutron-related
            r'/clusters/(?P<cluster_id>\d+)/network_configuration/neutron/?$',
            NeutronNetworkConfigurationHandler,
            r'/clusters/(?P<cluster_id>\d+)/network_configuration/'
            'neutron/verify/?$',
            NeutronNetworkConfigurationVerifyHandler,
        ) + super(NeutronNetworkPlugin,cls).get_urls()
        return urls
