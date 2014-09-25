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
import unittest2 as unittest

from random import randint

from nailgun.openstack.common import jsonutils
from nailgun.test.base import fake_tasks
from nailgun.test.performance.base import BaseUnitLoadTestCase


class ClusterOperationsLoadTest(BaseUnitLoadTestCase):

    @classmethod
    def setUpClass(cls):
        super(ClusterOperationsLoadTest, cls).setUpClass()
        cls.env.create_nodes(cls.NODES_NUM, cluster_id=cls.cluster['id'])

    def test_get_cluster(self):
        func = functools.partial(
            self.get_handler,
            'ClusterHandler',
            handler_kwargs={'obj_id': self.cluster['id']}
        )
        self.check_time_exec(func)

    def test_put_cluster(self):
        func = functools.partial(
            self.put_handler,
            'ClusterHandler',
            {'name': 'new_name'},
            handler_kwargs={'obj_id': self.cluster['id']}
        )
        self.check_time_exec(func)

    def test_get_default_deployment_info(self):
        func = functools.partial(
            self.get_handler,
            'DefaultDeploymentInfo',
            handler_kwargs={'cluster_id': self.cluster['id']}
        )
        self.check_time_exec(func, 70)

    def test_get_generated_data(self):
        func = functools.partial(
            self.get_handler,
            'ClusterGeneratedData',
            handler_kwargs={'cluster_id': self.cluster['id']}
        )
        self.check_time_exec(func)

    def test_get_default_provisioning_info(self):
        func = functools.partial(
            self.get_handler,
            'DefaultProvisioningInfo',
            handler_kwargs={'cluster_id': self.cluster['id']}
        )
        self.check_time_exec(func)

    def test_get_deployment_info(self):
        func = functools.partial(
            self.get_handler,
            'DeploymentInfo',
            handler_kwargs={'cluster_id': self.cluster['id']}
        )
        self.check_time_exec(func)

    def test_put_deployment_info(self):
        func = functools.partial(
            self.put_handler,
            'DeploymentInfo',
            [{'repo_metadata': 'new_data'}],
            handler_kwargs={'cluster_id': self.cluster['id']}
        )
        self.check_time_exec(func)

    def test_delete_deployment_info(self):
        func = functools.partial(
            self.delete_handler,
            'DeploymentInfo',
            handler_kwargs={'cluster_id': self.cluster['id']}
        )
        self.check_time_exec(func)

    def test_get_provisioning_info(self):
        func = functools.partial(
            self.get_handler,
            'ProvisioningInfo',
            handler_kwargs={'cluster_id': self.cluster['id']}
        )
        self.check_time_exec(func)

    def test_put_provisioning_info(self):
        func = functools.partial(
            self.put_handler,
            'ProvisioningInfo',
            {'field': 'new_info'},
            handler_kwargs={'cluster_id': self.cluster['id']}
        )
        self.check_time_exec(func)

    def test_delete_provisioning_info(self):
        func = functools.partial(
            self.delete_handler,
            'ProvisioningInfo',
            handler_kwargs={'cluster_id': self.cluster['id']}
        )
        self.check_time_exec(func)

    def test_get_clusters(self):
        func = functools.partial(
            self.get_handler,
            'ClusterCollectionHandler'
        )
        self.check_time_exec(func)

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
        self.check_time_exec(func)

    def test_get_attributes(self):
        func = functools.partial(
            self.get_handler,
            'ClusterAttributesHandler',
            handler_kwargs={'cluster_id': self.cluster['id']}
        )
        self.check_time_exec(func)

    def test_put_attributes(self):
        func = functools.partial(
            self.put_handler,
            'ClusterAttributesHandler',
            {'editable': {"foo": "bar"}},
            handler_kwargs={'cluster_id': self.cluster['id']}
        )
        self.check_time_exec(func)

    def test_patch_attributes(self):
        func = functools.partial(
            self.patch_handler,
            'ClusterAttributesHandler',
            {'editable': {'foo': 'bar'}},
            handler_kwargs={'cluster_id': self.cluster['id']}
        )
        self.check_time_exec(func)

    def test_get_default_attributes(self):
        func = functools.partial(
            self.get_handler,
            'ClusterAttributesDefaultsHandler',
            handler_kwargs={'cluster_id': self.cluster['id']}
        )
        self.check_time_exec(func)

    def test_put_default_attributes(self):
        func = functools.partial(
            self.put_handler,
            'ClusterAttributesDefaultsHandler',
            {'editable': {'foo': 'bar'}},
            handler_kwargs={'cluster_id': self.cluster['id']}
        )
        self.check_time_exec(func)

    @fake_tasks()
    def test_put_provision_selected_nodes(self):
        func = functools.partial(
            self.put_handler,
            'ProvisionSelectedNodes',
            [],
            handler_kwargs={'cluster_id': self.cluster['id']}
        )
        self.check_time_exec(func)

    @fake_tasks()
    def test_put_deploy_selected_nodes(self):
        func = functools.partial(
            self.put_handler,
            'DeploySelectedNodes',
            [],
            handler_kwargs={'cluster_id': self.cluster['id']}
        )
        self.check_time_exec(func, 10)

    @fake_tasks()
    def test_put_stop_deployment(self):
        self.put_handler(
            'DeploySelectedNodes',
            [],
            handler_kwargs={'cluster_id': self.cluster['id']}
        )
        func = functools.partial(
            self.put_handler,
            'ClusterStopDeploymentHandler',
            None,
            handler_kwargs={'cluster_id': self.cluster['id']}
        )
        self.check_time_exec(func)

    @unittest.skip("Skip it until ResetEnvironmentTaskManager.execute not "
                   "refactored to using objects with locking")
    @fake_tasks()
    def test_put_reset(self):
        func = functools.partial(
            self.put_handler,
            'ClusterResetHandler',
            None,
            handler_kwargs={'cluster_id': self.cluster['id']}
        )
        self.check_time_exec(func)

    def test_get_nova_network_configuration(self):
        func = functools.partial(
            self.get_handler,
            'NovaNetworkConfigurationHandler',
            handler_kwargs={'cluster_id': self.cluster['id']}
        )
        self.check_time_exec(func)

    def test_put_nova_network_configuration(self):
        resp = self.get_handler(
            'NovaNetworkConfigurationHandler',
            handler_kwargs={'cluster_id': self.cluster['id']}
        )
        self.assertEquals(200, resp.status_code)
        network_data = jsonutils.loads(resp.body)
        func = functools.partial(
            self.put_handler,
            'NovaNetworkConfigurationHandler',
            network_data,
            handler_kwargs={'cluster_id': self.cluster['id']}
        )
        self.check_time_exec(func)


class ClusterNeutronOperationsLoadTest(BaseUnitLoadTestCase):

    @classmethod
    def setUpClass(cls):
        super(ClusterNeutronOperationsLoadTest, cls).setUpClass()
        cls.cluster = cls.env.create_cluster(
            api=True,
            net_provider='neutron',
            net_segment_type='gre',
            mode='ha_compact')
        cls.env.create_nodes(cls.NODES_NUM, cluster_id=cls.cluster['id'])

    def test_get_neutron_network_configuration(self):
        func = functools.partial(
            self.get_handler,
            'NeutronNetworkConfigurationHandler',
            handler_kwargs={'cluster_id': self.cluster['id']}
        )
        self.check_time_exec(func)

    def test_put_neutron_network_configuration(self):
        resp = self.get_handler(
            'NeutronNetworkConfigurationHandler',
            handler_kwargs={'cluster_id': self.cluster['id']}
        )
        self.assertEquals(200, resp.status_code)
        network_data = jsonutils.loads(resp.body)
        func = functools.partial(
            self.put_handler,
            'NeutronNetworkConfigurationHandler',
            network_data,
            handler_kwargs={'cluster_id': self.cluster['id']}
        )
        self.check_time_exec(func)


class ClusterNodeOperationsLoadTest(BaseUnitLoadTestCase):

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
        self.check_time_exec(func)

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
        self.check_time_exec(func)
