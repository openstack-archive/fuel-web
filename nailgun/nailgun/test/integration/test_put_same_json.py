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

from mock import patch

from nailgun.openstack.common import jsonutils
from nailgun.test import base


class TestPutSameJson(base.BaseIntegrationTest):

    def setUp(self):
        super(TestPutSameJson, self).setUp()

        self.cluster = self.env.create(
            cluster_kwargs={'api': True},
            nodes_kwargs=[
                {'api': True},
                {'api': True, 'pending_addition': True},
            ]
        )
        self.cluster = self.env.clusters[0]

    def assertHttpPut(self, name, arguments, data, expected_status):
        """Helper assert for checking HTTP PUT.

        :param name: a handler name, for reversing url
        :param arguments: arguments for reversing url
        :param data: a data to be PUT
        :param expected_status: expected HTTP response code
        """
        response = self.app.put(
            base.reverse(name, kwargs=arguments),
            jsonutils.dumps(data),
            headers=self.default_headers
        )
        self.assertEqual(response.status_code, expected_status)

    def http_get(self, name, arguments):
        """Makes a GET request to a resource with `name`.
        Returns a deserialized dict.
        """
        resp = self.app.get(
            base.reverse(name, kwargs=arguments),
            headers=self.default_headers
        )
        return resp.json_body

    def test_release(self):
        release = self.env.create_release()
        release = self.http_get(
            'ReleaseHandler', {
                'obj_id': release['id']
            }
        )

        self.assertHttpPut(
            'ReleaseHandler', {
                'obj_id': release['id']
            },
            release, 200
        )

    def test_cluster(self):
        cluster = self.http_get(
            'ClusterHandler', {
                'obj_id': self.cluster.id
            }
        )

        self.assertHttpPut(
            'ClusterHandler', {
                'obj_id': self.cluster.id
            },
            cluster, 200
        )

    @patch('nailgun.rpc.cast')
    def test_cluster_changes(self, mock_rpc):
        cluster = self.http_get(
            'ClusterHandler', {
                'obj_id': self.cluster.id
            }
        )
        cluster_changes = cluster['changes']

        self.assertHttpPut(
            'ClusterChangesHandler',
            {
                'cluster_id': self.cluster.id
            },
            cluster_changes, 202
        )

    def test_cluster_attributes(self):
        cluster_attributes = self.http_get(
            'ClusterAttributesHandler', {
                'cluster_id': self.cluster.id
            }
        )

        self.assertHttpPut(
            'ClusterAttributesHandler', {
                'cluster_id': self.cluster.id
            },
            cluster_attributes, 200
        )

    def test_cluster_attributes_default(self):
        cluster_attributes = self.http_get(
            'ClusterAttributesDefaultsHandler', {
                'cluster_id': self.cluster.id
            }
        )

        self.assertHttpPut(
            'ClusterAttributesDefaultsHandler', {
                'cluster_id': self.cluster.id
            },
            cluster_attributes, 200
        )

    def test_nove_network_configuration(self):
        nova_config = self.http_get(
            'NovaNetworkConfigurationHandler', {
                'cluster_id': self.cluster.id
            }
        )

        self.assertHttpPut(
            'NovaNetworkConfigurationHandler', {
                'cluster_id': self.cluster.id
            },
            nova_config, 202
        )

    def test_neutron_network_configuration(self):
        self.cluster = self.env.create(
            cluster_kwargs={
                'api': True,
                'net_provider': 'neutron',
            },
            nodes_kwargs=[
                {'api': True},
                {'api': True},
            ]
        )

        neutron_config = self.http_get(
            'NeutronNetworkConfigurationHandler', {
                'cluster_id': self.cluster['id']
            }
        )

        self.assertHttpPut(
            'NeutronNetworkConfigurationHandler', {
                'cluster_id': self.cluster['id']
            },
            neutron_config, 200
        )

    def test_deployment_info(self):
        deployment_info = self.http_get(
            'DeploymentInfo', {
                'cluster_id': self.cluster.id
            }
        )

        self.assertHttpPut(
            'DeploymentInfo', {
                'cluster_id': self.cluster.id
            },
            deployment_info, 200
        )

    def test_provisioning_info(self):
        provisioning_info = self.http_get(
            'ProvisioningInfo', {
                'cluster_id': self.cluster.id
            }
        )

        self.assertHttpPut(
            'ProvisioningInfo', {
                'cluster_id': self.cluster.id
            },
            provisioning_info, 200
        )

    def test_node_collection(self):
        nodes = self.http_get(
            'NodeCollectionHandler', {}
        )

        self.assertHttpPut(
            'NodeCollectionHandler', {},
            nodes, 200
        )

    def test_node(self):
        node = self.http_get(
            'NodeHandler', {
                'obj_id': self.cluster.nodes[0].id
            }
        )

        self.assertHttpPut(
            'NodeHandler', {
                'obj_id': self.cluster.nodes[0].id
            },
            node, 200
        )

    def test_node_disks(self):
        node_disks = self.http_get(
            'NodeDisksHandler', {
                'node_id': self.cluster.nodes[0].id
            }
        )

        self.assertHttpPut(
            'NodeDisksHandler', {
                'node_id': self.cluster.nodes[0].id
            },
            node_disks, 200
        )

    def test_node_nics(self):
        node_nics = self.http_get(
            'NodeNICsHandler', {
                'node_id': self.cluster.nodes[0].id
            }
        )

        self.assertHttpPut(
            'NodeNICsHandler', {
                'node_id': self.cluster.nodes[0].id
            },
            node_nics, 200
        )

    def test_task(self):
        self.task = self.env.create_task(name='dump')

        task = self.http_get(
            'TaskHandler', {
                'obj_id': self.task.id
            }
        )

        self.assertHttpPut(
            'TaskHandler', {
                'obj_id': self.task.id
            },
            task, 200
        )

    def test_notification_collection(self):
        self.env.create_notification(cluster_id=self.cluster.id)
        self.env.create_notification(cluster_id=self.cluster.id)

        notifications = self.http_get(
            'NotificationCollectionHandler', {}
        )

        self.assertHttpPut(
            'NotificationCollectionHandler', {},
            notifications, 200
        )

    def test_notification(self):
        self.notification = self.env.create_notification(
            cluster_id=self.cluster.id
        )

        notification = self.http_get(
            'NotificationHandler', {
                'obj_id': self.notification.id
            }
        )

        self.assertHttpPut(
            'NotificationHandler', {
                'obj_id': self.notification.id
            },
            notification, 200
        )
