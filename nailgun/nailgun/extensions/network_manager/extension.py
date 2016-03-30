from nailgun.extensions import BaseExtension


class NetworkManagerExtension(BaseExtension):
    name = 'network_manager'
    version = '1.0.0'
    description = 'Network Manager'

    data_pipelines = []

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
