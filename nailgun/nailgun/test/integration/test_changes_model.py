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
from oslo_serialization import jsonutils

from nailgun import consts
from nailgun import objects

from nailgun.db.sqlalchemy.models import Cluster
from nailgun.db.sqlalchemy.models import ClusterChanges
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks
from nailgun.utils import reverse


class TestClusterChanges(BaseIntegrationTest):

    def test_cluster_creation_adds_pending_changes(self):
        self.env.create_cluster(api=True)
        attributes_changes = self.db.query(ClusterChanges).filter_by(
            name="attributes"
        ).all()
        self.assertEqual(len(attributes_changes), 1)
        networks_changes = self.db.query(ClusterChanges).filter_by(
            name="networks"
        ).all()
        self.assertEqual(len(networks_changes), 1)
        vmware_changes = self.db.query(ClusterChanges).filter_by(
            name="vmware_attributes"
        ).all()
        self.assertEqual(len(vmware_changes), 1)
        all_changes = self.db.query(ClusterChanges).all()
        self.assertEqual(len(all_changes), 3)

    def test_node_volumes_modification_adds_pending_changes(self):
        cluster = self.env.create_cluster(api=True)
        self.env.create_node(
            api=True,
            cluster_id=cluster["id"]
        )
        node_db = self.env.nodes[0]
        node_disks_changes = self.db.query(ClusterChanges).filter_by(
            name="disks",
            node_id=node_db.id
        ).all()
        self.assertEqual(len(node_disks_changes), 1)
        resp = self.app.get(
            reverse(
                'ClusterHandler',
                kwargs={'obj_id': cluster['id']}),
            headers=self.default_headers
        )
        self.assertIn(
            {"name": "disks", "node_id": node_db.id},
            resp.json_body["changes"]
        )

    def test_node_volumes_clears_after_deletion_from_cluster(self):
        cluster = self.env.create_cluster(api=True)
        self.env.create_node(
            api=True,
            cluster_id=cluster["id"]
        )
        node_db = self.env.nodes[0]
        node_disks_changes = self.db.query(ClusterChanges).filter_by(
            name="disks",
            node_id=node_db.id
        ).all()
        self.assertEqual(len(node_disks_changes), 1)
        self.app.put(
            reverse('NodeCollectionHandler'),
            jsonutils.dumps([{"id": node_db.id, "cluster_id": None}]),
            headers=self.default_headers
        )
        self.env.refresh_clusters()
        node_disks_changes = self.db.query(ClusterChanges).filter_by(
            name="disks",
            node_id=node_db.id
        ).all()
        self.assertEqual(len(node_disks_changes), 0)

    def test_attributes_changing_adds_pending_changes(self):
        cluster = self.env.create_cluster(api=True)
        cluster_db = self.env.clusters[0]
        objects.Cluster.clear_pending_changes(cluster_db)
        all_changes = self.db.query(ClusterChanges).all()
        self.assertEqual(len(all_changes), 0)
        self.app.put(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster['id']}),
            jsonutils.dumps({
                'editable': {
                    'foo': {'bar': None}
                }
            }),
            headers=self.default_headers
        )
        pending_changes = self.db.query(ClusterChanges).filter_by(
            name="attributes"
        ).all()
        self.assertEqual(len(pending_changes), 1)

    def test_default_attributes_adds_pending_changes(self):
        cluster = self.env.create_cluster(api=True)
        cluster_db = self.env.clusters[0]
        objects.Cluster.clear_pending_changes(cluster_db)
        all_changes = self.db.query(ClusterChanges).all()
        self.assertEqual(len(all_changes), 0)
        self.app.put(
            reverse(
                'ClusterAttributesDefaultsHandler',
                kwargs={'cluster_id': cluster['id']}),
            headers=self.default_headers
        )
        pending_changes = self.db.query(ClusterChanges).filter_by(
            name="attributes"
        ).all()
        self.assertEqual(len(pending_changes), 1)

    @fake_tasks(override_state={"progress": 100, "status": "ready"})
    def test_successful_deployment_drops_all_changes(self):
        self.env.create(
            nodes_kwargs=[
                {"api": True, "pending_addition": True}
            ]
        )
        supertask = self.env.launch_deployment()
        self.assertEqual(supertask.status, consts.TASK_STATUSES.ready)

        cluster_db = self.db.query(Cluster).get(
            self.env.clusters[0].id
        )
        self.assertEqual(list(cluster_db.changes), [])

    @fake_tasks(error="deployment", error_msg="Terrible error")
    def test_failed_deployment_does_nothing_with_changes(self):
        cluster = self.env.create_cluster(api=True)
        self.env.create_node(
            cluster_id=cluster["id"],
            status="error",
            error_type="provision",
            pending_roles=["controller"]
        )

        supertask = self.env.launch_deployment()
        self.assertEqual(supertask.status, consts.TASK_STATUSES.error)
        attributes_changes = self.db.query(ClusterChanges).filter_by(
            name="attributes"
        ).all()
        self.assertEqual(len(attributes_changes), 1)
        networks_changes = self.db.query(ClusterChanges).filter_by(
            name="networks"
        ).all()
        self.assertEqual(len(networks_changes), 1)
        vmware_changes = self.db.query(ClusterChanges).filter_by(
            name="vmware_attributes"
        ).all()
        self.assertEqual(len(vmware_changes), 1)
        disks_changes = self.db.query(ClusterChanges).filter_by(
            name="disks"
        ).all()
        self.assertEqual(len(disks_changes), 1)
        all_changes = self.db.query(ClusterChanges).all()
        self.assertEqual(len(all_changes), 5)

    @fake_tasks(override_state={"progress": 100, "status": "ready"})
    def test_role_unassignment_drops_changes(self):
        self.env.create(
            nodes_kwargs=[
                {"pending_addition": True, "api": True}
            ]
        )
        supertask = self.env.launch_deployment()
        self.assertEqual(supertask.status, consts.TASK_STATUSES.ready)
        new_node = self.env.create_node(
            cluster_id=self.env.clusters[0].id,
            pending_addition=True,
            api=True
        )
        self.app.put(
            reverse("NodeHandler",
                    kwargs={"obj_id": new_node["id"]}),
            jsonutils.dumps({
                "cluster": None,
                "pending_addition": False,
                "pending_roles": []
            }),
            headers=self.default_headers
        )
        all_changes = self.db.query(ClusterChanges).filter_by(
            cluster_id=self.env.clusters[0].id,
            node_id=new_node["id"]
        ).all()
        self.assertEqual(all_changes, [])
