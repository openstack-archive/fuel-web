from nailgun_network.network_plugin import NailgunNetworkPlugin, NovaNetworkConfigurationHandler, \
    NovaNetworkConfigurationVerifyHandler


class NovaNetworkPlugin(NailgunNetworkPlugin):

    __plugin_name__ = "nova_network_plugin"

    @classmethod
    def get_urls(cls):

        urls = (
            r'/clusters/(?P<cluster_id>\d+)/network_configuration/'
            'nova_network/?$',
            NovaNetworkConfigurationHandler,
            r'/clusters/(?P<cluster_id>\d+)/network_configuration/'
            'nova_network/verify/?$',
            NovaNetworkConfigurationVerifyHandler,
        ) + super(NovaNetworkPlugin,cls).get_urls()
        return urls