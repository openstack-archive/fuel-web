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

import yaml

from nailgun import consts
from nailgun.db import db
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
                            serialize_cluster(None, None)
                    }
                }]
            }
        )
        return rpc_message

    @classmethod
    def execute(cls, task):
        db().commit()
        rpc.cast(
            'naily',
            cls.message(task)
        )
