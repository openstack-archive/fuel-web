# -*- coding: utf-8 -*-

#    Copyright 2015 Mirantis, Inc.
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

import mock

from oslo_serialization import jsonutils

from nailgun import consts
from nailgun.test import base
from nailgun.utils import reverse

from . import base as tests_base


class TestClusterUpgradeCloneHandler(tests_base.BaseCloneClusterTest):
    def test_clone(self):
        resp = self.app.post(
            reverse("ClusterUpgradeCloneHandler",
                    kwargs={"cluster_id": self.src_cluster.id}),
            jsonutils.dumps(self.data),
            headers=self.default_headers)
        body = resp.json_body
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(body["name"],
                         "cluster-clone-{0}".format(self.src_cluster.id))
        self.assertEqual(body["release_id"], self.dst_release.id)

    def test_clone_cluster_not_found_error(self):
        resp = self.app.post(
            reverse("ClusterUpgradeCloneHandler",
                    kwargs={"cluster_id": 42}),
            jsonutils.dumps(self.data),
            headers=self.default_headers,
            expect_errors=True)
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json_body["message"], "Cluster not found")

    def test_clone_cluster_already_in_upgrade_error(self):
        self.app.post(
            reverse("ClusterUpgradeCloneHandler",
                    kwargs={"cluster_id": self.src_cluster.id}),
            jsonutils.dumps(self.data),
            headers=self.default_headers)
        resp = self.app.post(
            reverse("ClusterUpgradeCloneHandler",
                    kwargs={"cluster_id": self.src_cluster.id}),
            jsonutils.dumps(self.data),
            headers=self.default_headers,
            expect_errors=True)
        self.assertEqual(resp.status_code, 400)

    def test_clone_cluster_name_already_exists_error(self):
        data = dict(self.data, name=self.src_cluster.name)
        resp = self.app.post(
            reverse("ClusterUpgradeCloneHandler",
                    kwargs={"cluster_id": self.src_cluster.id}),
            jsonutils.dumps(data),
            headers=self.default_headers,
            expect_errors=True)
        self.assertEqual(resp.status_code, 409)


class TestNodeReassignHandler(base.BaseIntegrationTest):

    @mock.patch('nailgun.task.task.rpc.cast')
    def test_node_reassign_handler(self, mcast):
        cluster = self.env.create(
            cluster_kwargs={'api': False},
            nodes_kwargs=[{'status': consts.NODE_STATUSES.ready}])
        seed_cluster = self.env.create_cluster()
        node_id = cluster.nodes[0]['id']

        resp = self.app.post(
            reverse('NodeReassignHandler',
                    kwargs={'cluster_id': seed_cluster['id']}),
            jsonutils.dumps({'node_id': node_id}),
            headers=self.default_headers)
        self.assertEqual(202, resp.status_code)

        args, kwargs = mcast.call_args
        nodes = args[1]['args']['provisioning_info']['nodes']
        provisioned_uids = [int(n['uid']) for n in nodes]
        self.assertEqual([node_id, ], provisioned_uids)

    @mock.patch('nailgun.task.task.rpc.cast')
    def test_node_reassign_handler_with_roles(self, mcast):
        cluster = self.env.create(
            cluster_kwargs={'api': False},
            nodes_kwargs=[{'status': consts.NODE_STATUSES.ready,
                           'roles': ['controller']}])
        node = cluster.nodes[0]
        seed_cluster = self.env.create_cluster(api=False)

        # NOTE(akscram): reprovision=True means that the node will be
        #                re-provisioned during the reassigning. This is
        #                a default behavior.
        data = {'node_id': node.id,
                'reprovision': True,
                'roles': ['compute']}
        resp = self.app.post(
            reverse('NodeReassignHandler',
                    kwargs={'cluster_id': seed_cluster.id}),
            jsonutils.dumps(data),
            headers=self.default_headers)
        self.assertEqual(202, resp.status_code)
        self.assertEqual(node.roles, [])
        self.assertEqual(node.pending_roles, ['compute'])
        self.assertTrue(mcast.called)

    @mock.patch('nailgun.task.task.rpc.cast')
    def test_node_reassign_handler_without_reprovisioning(self, mcast):
        cluster = self.env.create(
            cluster_kwargs={'api': False},
            nodes_kwargs=[{'status': consts.NODE_STATUSES.ready,
                           'roles': ['controller']}])
        node = cluster.nodes[0]
        seed_cluster = self.env.create_cluster(api=False)

        data = {'node_id': node.id,
                'reprovision': False,
                'roles': ['compute']}
        resp = self.app.post(
            reverse('NodeReassignHandler',
                    kwargs={'cluster_id': seed_cluster.id}),
            jsonutils.dumps(data),
            headers=self.default_headers)
        self.assertEqual(200, resp.status_code)
        self.assertFalse(mcast.called)
        self.assertEqual(node.roles, ['compute'])

    def test_node_reassign_handler_no_node(self):
        cluster = self.env.create_cluster()

        resp = self.app.post(
            reverse('NodeReassignHandler',
                    kwargs={'cluster_id': cluster['id']}),
            jsonutils.dumps({'node_id': 42}),
            headers=self.default_headers,
            expect_errors=True)
        self.assertEqual(404, resp.status_code)
        self.assertEqual("Node with id 42 was not found.",
                         resp.json_body['message'])

    def test_node_reassing_handler_wrong_status(self):
        cluster = self.env.create(
            cluster_kwargs={'api': False},
            nodes_kwargs=[{'status': 'discover'}])

        resp = self.app.post(
            reverse('NodeReassignHandler',
                    kwargs={'cluster_id': cluster['id']}),
            jsonutils.dumps({'node_id': cluster.nodes[0]['id']}),
            headers=self.default_headers,
            expect_errors=True)
        self.assertEqual(400, resp.status_code)
        self.assertRegexpMatches(resp.json_body['message'],
                                 "^Node should be in one of statuses:")

    def test_node_reassing_handler_wrong_error_type(self):
        cluster = self.env.create(
            cluster_kwargs={'api': False},
            nodes_kwargs=[{'status': 'error',
                           'error_type': 'provision'}])

        resp = self.app.post(
            reverse('NodeReassignHandler',
                    kwargs={'cluster_id': cluster['id']}),
            jsonutils.dumps({'node_id': cluster.nodes[0]['id']}),
            headers=self.default_headers,
            expect_errors=True)
        self.assertEqual(400, resp.status_code)
        self.assertRegexpMatches(resp.json_body['message'],
                                 "^Node should be in error state")

    def test_node_reassign_handler_to_the_same_cluster(self):
        cluster = self.env.create(
            cluster_kwargs={'api': False},
            nodes_kwargs=[{'status': 'ready'}])

        cluster_id = cluster['id']
        node_id = cluster.nodes[0]['id']
        resp = self.app.post(
            reverse('NodeReassignHandler',
                    kwargs={'cluster_id': cluster_id}),
            jsonutils.dumps({'node_id': node_id}),
            headers=self.default_headers,
            expect_errors=True)
        self.assertEqual(400, resp.status_code)
        self.assertEqual("Node {0} is already assigned to cluster {1}".
                         format(node_id, cluster_id),
                         resp.json_body['message'])

    def test_node_reassign_handler_with_empty_data(self):
        cluster = self.env.create_cluster(api=False)
        resp = self.app.post(
            reverse('NodeReassignHandler',
                    kwargs={'cluster_id': cluster.id}),
            "{}",
            headers=self.default_headers,
            expect_errors=True)
        self.assertEqual(400, resp.status_code)

    def test_node_reassign_handler_with_empty_body(self):
        cluster = self.env.create_cluster(api=False)
        resp = self.app.post(
            reverse('NodeReassignHandler',
                    kwargs={'cluster_id': cluster.id}),
            "",
            headers=self.default_headers,
            expect_errors=True)
        self.assertEqual(400, resp.status_code)


class TestCopyVipsHandler(base.BaseIntegrationTest):

    def test_copy_vips_called(self):
        from ..objects import relations

        orig_cluster = self.env.create_cluster(api=False)
        new_cluster = self.env.create_cluster(api=False)

        relations.UpgradeRelationObject.create_relation(
            orig_cluster.id, new_cluster.id)

        with mock.patch('nailgun.extensions.cluster_upgrade.handlers'
                        '.upgrade.UpgradeHelper.copy_vips') as copy_vips_mc:
            resp = self.app.post(
                reverse(
                    'CopyVIPsHandler',
                    kwargs={'cluster_id': new_cluster.id}
                ),
                headers=self.default_headers,
            )

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(copy_vips_mc.called)
