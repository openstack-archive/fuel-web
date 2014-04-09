# -*- coding: utf-8 -*-

#    Copyright 2013 Mirantis, Inc.
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

import json
from mock import patch

import nailgun
from nailgun.db.sqlalchemy.models import Cluster
from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun.db.sqlalchemy.models import Node
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks
from nailgun.test.base import reverse


class TestHandlers(BaseIntegrationTest):

    def delete(self, cluster_id):
        return self.app.delete(
            reverse('ClusterHandler', kwargs={'obj_id': cluster_id}),
            '',
            headers=self.default_headers
        )

    def test_cluster_get(self):
        cluster = self.env.create_cluster(api=False)
        resp = self.app.get(
            reverse('ClusterHandler', kwargs={'obj_id': cluster.id}),
            headers=self.default_headers
        )
        self.assertEquals(200, resp.status_code)
        response = json.loads(resp.body)
        self.assertEquals(cluster.id, response['id'])
        self.assertEquals(cluster.name, response['name'])
        self.assertEquals(cluster.release.id, response['release_id'])

    def test_cluster_creation(self):
        release = self.env.create_release(api=False)
        yet_another_cluster_name = 'Yet another cluster'
        resp = self.app.post(
            reverse('ClusterCollectionHandler'),
            params=json.dumps({
                'name': yet_another_cluster_name,
                'release': release.id
            }),
            headers=self.default_headers
        )
        self.assertEquals(201, resp.status_code)
        response = json.loads(resp.body)
        self.assertEquals(yet_another_cluster_name, response['name'])
        self.assertEquals(release.id, response['release_id'])

    def test_cluster_update(self):
        updated_name = u'Updated cluster'
        cluster = self.env.create_cluster(api=False)

        clusters_before = len(self.db.query(Cluster).all())

        resp = self.app.patch(
            reverse('ClusterHandler', kwargs={'obj_id': cluster.id}),
            json.dumps({'name': updated_name}),
            headers=self.default_headers
        )
        self.db.refresh(cluster)
        self.assertEquals(resp.status_code, 200)
        clusters = self.db.query(Cluster).filter(
            Cluster.name == updated_name
        ).all()
        self.assertEquals(len(clusters), 1)
        self.assertEquals(clusters[0].name, updated_name)

        clusters_after = len(self.db.query(Cluster).all())
        self.assertEquals(clusters_before, clusters_after)

    def test_cluster_updates_network_manager(self):
        cluster = self.env.create_cluster(api=False)
        self.assertEquals(cluster.net_manager, "FlatDHCPManager")
        resp = self.app.patch(
            reverse('ClusterHandler', kwargs={'obj_id': cluster.id}),
            json.dumps({'net_manager': 'VlanManager'}),
            headers=self.default_headers
        )
        self.assertEquals(resp.status_code, 200)
        self.db.refresh(cluster)
        self.assertEquals(cluster.net_manager, "VlanManager")

    def test_cluster_update_fails_on_net_provider_change(self):
        cluster = self.env.create_cluster(api=False)
        self.assertEquals(cluster.net_provider, "nova_network")
        resp = self.app.patch(
            reverse('ClusterHandler', kwargs={'obj_id': cluster.id}),
            json.dumps({'net_provider': 'neutron'}),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEquals(resp.status_code, 400)
        self.assertEquals(
            resp.body,
            "Changing 'net_provider' for environment is prohibited"
        )

    def test_cluster_update_fails_on_net_segment_type_change(self):
        cluster = self.env.create_cluster(
            api=False,
            net_provider='neutron',
            net_segment_type='gre'
        )
        self.assertEquals(cluster.net_provider, "neutron")
        resp = self.app.patch(
            reverse('ClusterHandler', kwargs={'obj_id': cluster.id}),
            json.dumps({'net_segment_type': 'vlan'}),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEquals(resp.status_code, 400)
        self.assertEquals(
            resp.body,
            "Changing 'net_segment_type' for environment is prohibited"
        )

    def test_cluster_node_list_update(self):
        node1 = self.env.create_node(api=False)
        node2 = self.env.create_node(api=False)
        cluster = self.env.create_cluster(api=False)
        resp = self.app.patch(
            reverse('ClusterHandler', kwargs={'obj_id': cluster.id}),
            json.dumps({'nodes': [node1.id]}),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEquals(resp.status_code, 200)

        nodes = self.db.query(Node).filter(Node.cluster == cluster).all()
        self.assertEquals(1, len(nodes))
        self.assertEquals(nodes[0].id, node1.id)

        resp = self.app.patch(
            reverse('ClusterHandler', kwargs={'obj_id': cluster.id}),
            json.dumps({'nodes': [node2.id]}),
            headers=self.default_headers
        )
        self.assertEquals(resp.status_code, 200)

        nodes = self.db.query(Node).filter(Node.cluster == cluster)
        self.assertEquals(1, nodes.count())

    def test_empty_cluster_deletion(self):
        cluster = self.env.create_cluster(api=True)
        resp = self.delete(cluster['id'])

        self.assertEquals(resp.status_code, 202)
        self.assertEquals(self.db.query(Node).count(), 0)
        self.assertEquals(self.db.query(Cluster).count(), 0)

    @fake_tasks()
    def test_cluster_deletion(self):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"pending_addition": True},
                {"status": "ready"}])

        resp = self.delete(self.env.clusters[0].id)
        self.assertEquals(resp.status_code, 202)

        def cluster_is_empty():
            return self.db.query(Cluster).count() == 0

        self.env.wait_for_true(cluster_is_empty, timeout=5)
        self._wait_for_threads()

        # Nodes should be in discover status
        self.assertEquals(self.db.query(Node).count(), 2)
        for node in self.db.query(Node):
            self.assertEquals(node.status, 'discover')
            self.assertEquals(node.cluster_id, None)

    @fake_tasks()
    def test_cluster_deletion_with_offline_nodes(self):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {'pending_addition': True},
                {'online': False, 'status': 'ready'}])

        resp = self.delete(self.env.clusters[0].id)
        self.assertEquals(resp.status_code, 202)

        def cluster_is_empty_and_in_db_one_node():
            return self.db.query(Cluster).count() == 0 and \
                self.db.query(Node).count() == 1

        self.env.wait_for_true(cluster_is_empty_and_in_db_one_node, timeout=5)
        self._wait_for_threads()

        node = self.db.query(Node).first()
        self.assertEquals(node.status, 'discover')
        self.assertEquals(node.cluster_id, None)

    def test_cluster_deletion_delete_networks(self):
        cluster = self.env.create_cluster(api=True)
        cluster_db = self.db.query(Cluster).get(cluster['id'])
        ngroups = [n.id for n in cluster_db.network_groups]
        self.db.delete(cluster_db)
        self.db.commit()
        ngs = self.db.query(NetworkGroup).filter(
            NetworkGroup.id.in_(ngroups)
        ).all()
        self.assertEqual(ngs, [])

    @fake_tasks(fake_rpc=False, mock_rpc=False)
    @patch('nailgun.rpc.cast')
    def test_replaced_orchestrator_info_should_passed(self, mocked_rpc):
        # creating cluster with nodes
        self.env.create(
            cluster_kwargs={
                'mode': 'multinode'},
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True},
                {'roles': ['compute'], 'pending_addition': True}])
        cluster = self.env.clusters[0]
        new_deployment_info = {"field": "deployment_info"}
        new_provisioning_info = {"field": "provisioning_info"}

        # assigning facts to cluster
        cluster.replaced_deployment_info = new_deployment_info
        cluster.replaced_provisioning_info = new_provisioning_info
        self.db.commit()
        self.env.launch_deployment()

        # intercepting arguments with which rpc.cast was called
        args, kwargs = nailgun.task.manager.rpc.cast.call_args
        self.datadiff(
            new_provisioning_info, args[1][0]['args']['provisioning_info'])
        self.datadiff(
            new_deployment_info, args[1][1]['args']['deployment_info'])

    def test_cluster_generated_data_handler(self):
        self.env.create(
            nodes_kwargs=[
                {'pending_addition': True},
                {'online': False, 'status': 'ready'}])
        cluster = self.env.clusters[0]
        get_resp = self.app.get(
            reverse('ClusterGeneratedData',
                    kwargs={'cluster_id': cluster.id}),
            headers=self.default_headers
        )
        self.assertEquals(get_resp.status_code, 200)
        self.datadiff(json.loads(get_resp.body), cluster.attributes.generated)
