from nailgun.extensions import BaseExtension


class NetworkManagerExtension(BaseExtension):
    name = 'network_manager'
    version = '1.0.0'
    description = 'Network Manager'

    data_pipelines = []
