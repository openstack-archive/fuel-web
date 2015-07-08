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

from oslo.serialization import jsonutils

from nailgun.db.sqlalchemy.models import Cluster
from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun.db.sqlalchemy.models import Node
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks
from nailgun.utils import reverse


class TestHandlers(BaseIntegrationTest):

    def delete(self, cluster_id):
        return self.app.delete(
            reverse('ClusterHandler', kwargs={'obj_id': cluster_id}),
            headers=self.default_headers
        )

    def test_cluster_get(self):
        cluster = self.env.create_cluster(api=False)
        resp = self.app.get(
            reverse('ClusterHandler', kwargs={'obj_id': cluster.id}),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        self.assertEqual(cluster.id, resp.json_body['id'])
        self.assertEqual(cluster.name, resp.json_body['name'])
        self.assertEqual(cluster.release.id, resp.json_body['release_id'])

    def test_cluster_creation(self):
        release = self.env.create_release(api=False)
        yet_another_cluster_name = 'Yet another cluster'
        resp = self.app.post(
            reverse('ClusterCollectionHandler'),
            params=jsonutils.dumps({
                'name': yet_another_cluster_name,
                'release': release.id
            }),
            headers=self.default_headers
        )
        self.assertEqual(201, resp.status_code)
        self.assertEqual(yet_another_cluster_name, resp.json_body['name'])
        self.assertEqual(release.id, resp.json_body['release_id'])

    def test_cluster_update(self):
        updated_name = u'Updated cluster'
        cluster = self.env.create_cluster(api=False)

        clusters_before = len(self.db.query(Cluster).all())

        resp = self.app.put(
            reverse('ClusterHandler', kwargs={'obj_id': cluster.id}),
            jsonutils.dumps({'name': updated_name}),
            headers=self.default_headers
        )
        self.db.refresh(cluster)
        self.assertEqual(resp.status_code, 200)
        clusters = self.db.query(Cluster).filter(
            Cluster.name == updated_name
        ).all()
        self.assertEqual(len(clusters), 1)
        self.assertEqual(clusters[0].name, updated_name)

        clusters_after = len(self.db.query(Cluster).all())
        self.assertEqual(clusters_before, clusters_after)

    def test_cluster_update_fails_on_net_provider_change(self):
        cluster = self.env.create_cluster(api=False)
        self.assertEqual(cluster.net_provider, "nova_network")
        resp = self.app.put(
            reverse('ClusterHandler', kwargs={'obj_id': cluster.id}),
            jsonutils.dumps({'net_provider': 'neutron'}),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            resp.json_body["message"],
            "Changing 'net_provider' for environment is prohibited"
        )

    def test_cluster_node_list_update(self):
        node1 = self.env.create_node(api=False, hostname='name1')
        cluster = self.env.create_cluster(api=False)
        resp = self.app.put(
            reverse('ClusterHandler', kwargs={'obj_id': cluster.id}),
            jsonutils.dumps({'nodes': [node1.id]}),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 200)
        node2 = self.env.create_node(api=False, hostname='name1')

        nodes = self.db.query(Node).filter(Node.cluster == cluster).all()
        self.assertEqual(1, len(nodes))
        self.assertEqual(nodes[0].id, node1.id)

        resp = self.app.put(
            reverse('ClusterHandler', kwargs={'obj_id': cluster.id}),
            jsonutils.dumps({'nodes': [node2.id]}),
            headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 200)

        self.assertEqual('node-{0}'.format(node1.id), node1.hostname)

        nodes = self.db.query(Node).filter(Node.cluster == cluster)
        self.assertEqual(1, nodes.count())

    def test_cluster_node_list_update_error(self):
        node1 = self.env.create_node(api=False, hostname='name1')
        cluster = self.env.create_cluster(api=False)
        self.app.put(
            reverse('ClusterHandler', kwargs={'obj_id': cluster.id}),
            jsonutils.dumps({'nodes': [node1.id]}),
            headers=self.default_headers,
            expect_errors=True
        )
        node2 = self.env.create_node(api=False, hostname='name1')

        # try to add to cluster one more node with the same hostname
        resp = self.app.put(
            reverse('ClusterHandler', kwargs={'obj_id': cluster.id}),
            jsonutils.dumps({'nodes': [node1.id, node2.id]}),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 400)

    def test_empty_cluster_deletion(self):
        cluster = self.env.create_cluster(api=True)
        resp = self.delete(cluster['id'])

        self.assertEqual(resp.status_code, 202)
        self.assertEqual(self.db.query(Node).count(), 0)
        self.assertEqual(self.db.query(Cluster).count(), 0)

    @fake_tasks()
    def test_cluster_deletion(self):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {"pending_addition": True},
                {"status": "ready"}])

        resp = self.delete(self.env.clusters[0].id)
        self.assertEqual(resp.status_code, 202)

        def cluster_is_empty():
            return self.db.query(Cluster).count() == 0

        self.env.wait_for_true(cluster_is_empty, timeout=5)
        self._wait_for_threads()

        # Nodes should be in discover status
        self.assertEqual(self.db.query(Node).count(), 2)
        for node in self.db.query(Node):
            self.assertEqual(node.status, 'discover')
            self.assertEqual(node.cluster_id, None)
            self.assertEqual(node.group_id, None)
            self.assertEqual(node.roles, [])
            self.assertFalse(node.pending_deletion)
            self.assertFalse(node.pending_addition)

    @fake_tasks(recover_offline_nodes=False)
    def test_cluster_deletion_with_offline_nodes(self):
        self.env.create(
            cluster_kwargs={},
            nodes_kwargs=[
                {'pending_addition': True},
                {'online': False, 'status': 'ready'}])

        resp = self.delete(self.env.clusters[0].id)
        self.assertEqual(resp.status_code, 202)

        def cluster_is_empty_and_in_db_one_node():
            return self.db.query(Cluster).count() == 0 and \
                self.db.query(Node).count() == 1

        self.env.wait_for_true(cluster_is_empty_and_in_db_one_node, timeout=5)
        self._wait_for_threads()

        node = self.db.query(Node).first()
        self.assertEqual(node.status, 'discover')
        self.assertEqual(node.cluster_id, None)

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
        self.assertEqual(get_resp.status_code, 200)
        self.datadiff(get_resp.json_body, cluster.attributes.generated)

    def test_cluster_name_length(self):
        long_name = u'ю' * 2048
        cluster = self.env.create_cluster(api=False)

        resp = self.app.put(
            reverse('ClusterHandler', kwargs={'obj_id': cluster.id}),
            jsonutils.dumps({'name': long_name}),
            headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 200)
        self.db.refresh(cluster)
        self.assertEqual(long_name, cluster.name)
