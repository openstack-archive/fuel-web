# -*- coding: utf-8 -*-
#    Copyright 2014 Mirantis, Inc.
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

import functools
from random import randint
import unittest

from nailgun.openstack.common import jsonutils
from nailgun.test.base import fake_tasks
from nailgun.test.load.increasing_workload.base_load import BaseLoadTestCase


class ClusterOperationsLoadTest(BaseLoadTestCase):

    def test_get_cluster(self):
        cluster_id = self.env.create_cluster()['id']
        func = functools.partial(
            self.get_handler,
            'ClusterHandler',
            cluster_id
        )
        times = self.growing_nodes_executor(func, cluster_id=cluster_id)
        self.check_degradation(times)

    def test_put_cluster(self):
        cluster_id = self.env.create_cluster()['id']
        func = functools.partial(
            self.put_handler,
            'ClusterHandler',
            {'name': 'new_name'},
            handler_kwargs={'obj_id': cluster_id}
        )
        times = self.growing_nodes_executor(func)
        self.check_degradation(times)

    def test_get_default_deployment_info(self):
        cluster_id = self.env.create_cluster()['id']
        func = functools.partial(
            self.get_handler,
            'DefaultDeploymentInfo',
            cluster_id,
            id_name='cluster_id'
        )
        times = self.growing_nodes_executor(
            func,
            max_exec_time=1.0,
            cluster_id=cluster_id,
            pending_addition=True
        )
        self.check_degradation(times)

    def test_get_generated_data(self):
        cluster_id = self.env.create_cluster()['id']
        func = functools.partial(
            self.get_handler,
            'ClusterGeneratedData',
            cluster_id,
            id_name='cluster_id'
        )
        times = self.growing_nodes_executor(func, cluster_id=cluster_id)
        self.check_degradation(times)

    def test_get_default_provisioning_info(self):
        cluster_id = self.env.create_cluster()['id']
        func = functools.partial(
            self.get_handler,
            'DefaultProvisioningInfo',
            cluster_id,
            id_name='cluster_id'
        )
        times = self.growing_nodes_executor(func, cluster_id=cluster_id)
        self.check_degradation(times)

    def test_get_deployment_info(self):
        cluster_id = self.env.create_cluster()['id']
        func = functools.partial(
            self.get_handler,
            'DeploymentInfo',
            cluster_id,
            id_name='cluster_id'
        )
        times = self.growing_nodes_executor(
            func,
            cluster_id=cluster_id,
            replaced_deployment_info=[{'repo_metadata': 'data'}]
        )
        self.check_degradation(times)

    def test_put_deployment_info(self):
        cluster_id = self.env.create_cluster()['id']
        func = functools.partial(
            self.put_handler,
            'DeploymentInfo',
            [{'repo_metadata': 'new_data'}],
            handler_kwargs={'cluster_id': cluster_id}
        )
        times = self.growing_nodes_executor(
            func,
            cluster_id=cluster_id,
            replaced_deployment_info=[{'repo_metadata': 'data'}]
        )
        self.check_degradation(times)

    def test_delete_deployment_info(self):
        cluster_id = self.env.create_cluster()['id']
        func = functools.partial(
            self.delete_handler,
            'DeploymentInfo',
            cluster_id,
            id_name='cluster_id'
        )
        times = self.growing_nodes_executor(
            func,
            cluster_id=cluster_id,
            replaced_deployment_info=[{'repo_metadata': 'data'}]
        )
        self.check_degradation(times)

    def test_get_provisioning_info(self):
        cluster_id = self.env.create_cluster(
            replaced_provisioning_info={
                'field': 'info',
            }
        )['id']
        func = functools.partial(
            self.get_handler,
            'ProvisioningInfo',
            cluster_id,
            id_name='cluster_id'
        )
        times = self.growing_nodes_executor(
            func,
            cluster_id=cluster_id,
            replaced_provisioning_info={'field': 'info'}
        )
        self.check_degradation(times)

    def test_put_provisioning_info(self):
        cluster_id = self.env.create_cluster()['id']
        func = functools.partial(
            self.put_handler,
            'ProvisioningInfo',
            {'field': 'new_info'},
            handler_kwargs={'cluster_id': cluster_id}
        )
        times = self.growing_nodes_executor(
            func,
            cluster_id=cluster_id,
            replaced_provisioning_info={'field': 'info'}
        )
        self.check_degradation(times)

    def test_delete_provisioning_info(self):
        cluster_id = self.env.create_cluster()['id']
        func = functools.partial(
            self.delete_handler,
            'ProvisioningInfo',
            cluster_id,
            id_name='cluster_id'
        )
        times = self.growing_nodes_executor(
            func,
            cluster_id=cluster_id,
            replaced_provisioning_info={'field': 'info'}
        )
        self.check_degradation(times)

    def test_get_clusters(self):
        cluster_id = self.env.create_cluster()['id']
        func = functools.partial(
            self.get_handler,
            'ClusterCollectionHandler',
            None
        )
        times = self.growing_nodes_executor(func, cluster_id=cluster_id)
        self.check_degradation(times)

    def post_cluster(self, release_id):
        cluster_data = {
            'name': 'n-{0}'.format(randint(0, 1000000)),
            'release_id': release_id
        }
        return self.post_handler(
            'ClusterCollectionHandler',
            cluster_data
        )

    def test_post_cluster(self):
        release = self.env.create_release()
        func = functools.partial(self.post_cluster, release.id)
        times = self.growing_nodes_executor(func)
        self.check_degradation(times)

    @fake_tasks()
    def test_put_cluster_changes(self):
        cluster_id = self.env.create_cluster()['id']
        func = functools.partial(
            self.put_handler,
            'ClusterChangesHandler',
            [],
            handler_kwargs={'cluster_id': cluster_id}
        )
        times = self.growing_nodes_executor(
            func,
            max_exec_time=2.0,
            cluster_id=cluster_id,
            pending_addition=True
        )
        self.check_degradation(times)

    def test_get_attributes(self):
        cluster_id = self.env.create_cluster()['id']
        func = functools.partial(
            self.get_handler,
            'ClusterAttributesHandler',
            cluster_id,
            id_name='cluster_id'
        )
        times = self.growing_nodes_executor(
            func,
            cluster_id=cluster_id,
        )
        self.check_degradation(times)

    def test_put_attributes(self):
        cluster_id = self.env.create_cluster()['id']
        func = functools.partial(
            self.put_handler,
            'ClusterAttributesHandler',
            {'editable': {"foo": "bar"}},
            handler_kwargs={'cluster_id': cluster_id}
        )
        times = self.growing_nodes_executor(func, cluster_id=cluster_id)
        self.check_degradation(times)

    def test_patch_attributes(self):
        cluster_id = self.env.create_cluster()['id']
        func = functools.partial(
            self.patch_handler,
            'ClusterAttributesHandler',
            {'editable': {'foo': 'bar'}},
            handler_kwargs={'cluster_id': cluster_id}
        )
        times = self.growing_nodes_executor(func, cluster_id=cluster_id)
        self.check_degradation(times)

    def test_get_default_attributes(self):
        cluster_id = self.env.create_cluster()['id']
        func = functools.partial(
            self.get_handler,
            'ClusterAttributesDefaultsHandler',
            cluster_id,
            id_name='cluster_id'
        )
        times = self.growing_nodes_executor(func, cluster_id=cluster_id)
        self.check_degradation(times)

    def test_put_default_attributes(self):
        cluster_id = self.env.create_cluster()['id']
        func = functools.partial(
            self.put_handler,
            'ClusterAttributesDefaultsHandler',
            {'editable': {'foo': 'bar'}},
            handler_kwargs={'cluster_id': cluster_id}
        )
        times = self.growing_nodes_executor(func, cluster_id=cluster_id)
        self.check_degradation(times)

    @fake_tasks()
    def test_put_provision_selected_nodes(self):
        cluster_id = self.env.create_cluster()['id']
        func = functools.partial(
            self.put_handler,
            'ProvisionSelectedNodes',
            [],
            handler_kwargs={'cluster_id': cluster_id}
        )
        times = self.growing_nodes_executor(
            func,
            cluster_id=cluster_id,
            pending_addition=True
        )
        self.check_degradation(times)

    @fake_tasks()
    def test_put_deploy_selected_nodes(self):
        cluster_id = self.env.create_cluster()['id']
        func = functools.partial(
            self.put_handler,
            'DeploySelectedNodes',
            [],
            handler_kwargs={'cluster_id': cluster_id}
        )
        times = self.growing_nodes_executor(
            func,
            cluster_id=cluster_id,
            pending_addition=True
        )
        self.check_degradation(times)

    @fake_tasks()
    def test_put_stop_deployment(self):
        cluster_id = self.env.create_cluster()['id']
        self.put_handler(
            'DeploySelectedNodes',
            [],
            handler_kwargs={'cluster_id': cluster_id}
        )
        func = functools.partial(
            self.put_handler,
            'ClusterStopDeploymentHandler',
            None,
            handler_kwargs={'cluster_id': cluster_id}
        )
        times = self.growing_nodes_executor(
            func,
            cluster_id=cluster_id,
            pending_addition=True
        )
        self.check_degradation(times)

    @unittest.skip("Skip it until ResetEnvironmentTaskManager.execute not "
                   "refactored to using objects with locking")
    @fake_tasks()
    def test_put_reset(self):
        cluster_id = self.env.create_cluster()['id']
        func = functools.partial(
            self.put_handler,
            'ClusterResetHandler',
            None,
            handler_kwargs={'cluster_id': cluster_id}
        )
        times = self.growing_nodes_executor(
            func,
            cluster_id=cluster_id,
            pending_addition=True
        )
        self.check_degradation(times)

    def assign_node(self, cluster_id):
        node = self.env.create_node()
        return self.post_handler(
            'NodeAssignmentHandler',
            [{'id': node.id, 'roles': ['compute']}],
            handler_kwargs={'cluster_id': cluster_id}
        )

    def test_post_node_assingment(self):
        cluster_id = self.env.create_cluster()['id']
        func = functools.partial(self.assign_node, cluster_id)
        times = self.growing_nodes_executor(
            func,
            cluster_id=cluster_id,
            pending_addition=True
        )
        self.check_degradation(times)

    def unassign_node(self, cluster_id):
        node = self.env.create_node(cluster_id=cluster_id)
        return self.post_handler(
            'NodeUnassignmentHandler',
            [{'id': node.id}],
            handler_kwargs={'cluster_id': cluster_id}
        )

    def test_post_node_unassingment(self):
        cluster_id = self.env.create_cluster()['id']
        func = functools.partial(self.unassign_node, cluster_id)
        times = self.growing_nodes_executor(
            func,
            cluster_id=cluster_id,
            pending_addition=True
        )
        self.check_degradation(times)

    def test_get_nova_network_configuration(self):
        cluster_id = self.env.create_cluster()['id']
        func = functools.partial(
            self.get_handler,
            'NovaNetworkConfigurationHandler',
            cluster_id,
            id_name='cluster_id'
        )
        times = self.growing_nodes_executor(func, cluster_id=cluster_id)
        self.check_degradation(times)

    def test_put_nova_network_configuration(self):
        cluster_id = self.env.create_cluster()['id']
        resp = self.get_handler(
            'NovaNetworkConfigurationHandler',
            cluster_id,
            id_name='cluster_id'
        )
        self.assertEquals(200, resp.status_code)
        network_data = jsonutils.loads(resp.body)
        func = functools.partial(
            self.put_handler,
            'NovaNetworkConfigurationHandler',
            network_data,
            handler_kwargs={'cluster_id': cluster_id}
        )
        times = self.growing_nodes_executor(func, cluster_id=cluster_id)
        self.check_degradation(times)

    def test_get_neutron_network_configuration(self):
        cluster = self.env.create_cluster(net_provider='neutron')
        cluster_id = cluster['id']
        func = functools.partial(
            self.get_handler,
            'NeutronNetworkConfigurationHandler',
            cluster_id,
            id_name='cluster_id'
        )
        times = self.growing_nodes_executor(func, cluster_id=cluster_id)
        self.check_degradation(times)

    def test_put_neutron_network_configuration(self):
        cluster = self.env.create_cluster(net_provider='neutron')
        cluster_id = cluster['id']
        resp = self.get_handler(
            'NeutronNetworkConfigurationHandler',
            cluster_id,
            id_name='cluster_id'
        )
        self.assertEquals(200, resp.status_code)
        network_data = jsonutils.loads(resp.body)
        func = functools.partial(
            self.put_handler,
            'NeutronNetworkConfigurationHandler',
            network_data,
            handler_kwargs={'cluster_id': cluster_id}
        )
        times = self.growing_nodes_executor(func, cluster_id=cluster_id)
        self.check_degradation(times)
