import yaml

from nailgun import consts
from nailgun import objects
from nailgun.orchestrator import provisioning_serializers
import nailgun.rpc as rpc
from nailgun.task import task as tasks


class UpdateDnsmasqTask(object):

    @classmethod
    def get_admin_networks_data(cls):
        nm = objects.Cluster.get_network_manager()
        return {'admin_networks': nm.get_admin_networks(True)}

    @classmethod
    def message(cls, task):
        rpc_message = tasks.make_astute_message(
            task,
            'execute_tasks',
            'base_resp',
            {
                'tasks': [{
                    'type': consts.ORCHESTRATOR_TASK_TYPES.upload_file,
                    'uids': ['master'],
                    'parameters': {
                        'path': '/etc/hiera/networks.yaml',
                        'data': yaml.safe_dump(cls.get_admin_networks_data())}
                }, {
                    'type': consts.ORCHESTRATOR_TASK_TYPES.puppet,
                    'uids': ['master'],
                    'parameters': {
                        'puppet_modules': '/etc/puppet/modules',
                        'puppet_manifest': '/etc/puppet/modules/fuel/'
                                           'examples/dhcp-ranges.pp',
                        'timeout': 300,
                        'cwd': '/'}
                }, {
                    'type': 'cobbler_sync',
                    'uids': ['master'],
                    'parameters': {
                        'provisioning_info':
                            provisioning_serializers.ProvisioningSerializer.
                            serialize_cluster_info(None, None)
                    }
                }]
            }
        )
        return rpc_message

    @classmethod
    def execute(cls, task):
        rpc.cast(
            'naily',
            cls.message(task)
        )
