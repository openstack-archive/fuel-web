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

from oslo.serialization import jsonutils

from nailgun import consts
from nailgun import objects
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import reverse


class TestVMs(BaseIntegrationTest):

    def setUp(self):
        super(TestVMs, self).setUp()
        self.cluster = self.env.create(
            cluster_kwargs={'api': False},
            nodes_kwargs=[
                {'roles': ['compute']},
                {'roles': ['compute']},
                {'roles': ['compute']}])

    def test_create_vms(self):
        self.app.post(reverse(
            'VirtualMachinesRequestHandler',
            kwargs={'obj_id': self.cluster.nodes[0].id}),
            jsonutils.dumps({'vms_number': 2}))
        resp = self.app.get(reverse(
            'VirtualMachinesRequestHandler',
            kwargs={'obj_id': self.cluster.nodes[0].id}))
        self.assertEqual(len(resp.json), 2)


class TestPredeploymentVMs(BaseIntegrationTest):

    def setUp(self):
        super(TestPredeploymentVMs, self).setUp()
        self.cluster = self.env.create(
            cluster_kwargs={'api': False},
            nodes_kwargs=[
                {'roles': ['compute']},
                {'roles': ['compute']},
                {'roles': ['compute']}])
        objects.VirtualMachinesRequestsCollection.create(
            {'node_id': self.cluster.nodes[0].id,
             'cluster_id': self.cluster.id})
        objects.VirtualMachinesRequestsCollection.create(
            {'node_id': self.cluster.nodes[1].id,
             'cluster_id': self.cluster.id})
        self.node_uids = [str(self.cluster.nodes[0].id),
                          str(self.cluster.nodes[1].id)]

    @mock.patch('nailgun.orchestrator.tasks_serializer.open', create=True)
    @mock.patch('nailgun.task.task.rpc.cast')
    def test_prepare_deploy(self, mcast, m_open):
        m_open.side_effect = lambda *args: mock.mock_open(
            read_data='<tag>{cluster_id}</tag><tag>{empty_value}</tag>')()
        for node in self.cluster.nodes:
            node.status = consts.NODE_STATUSES.provisioned
            node.pending_addition = False

        self.db.add_all(self.cluster.nodes)
        self.db.flush()
        out = self.app.put(reverse(
            "PrepareDeployHandler", kwargs={'cluster_id': self.cluster.id}))
        self.assertEqual(out.status_code, 202)

        args, kwargs = mcast.call_args
        deployed_uids = [n['uid'] for n in args[1]['args']['deployment_info']]
        self.assertListEqual(deployed_uids, self.node_uids)
