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

from nailgun import consts
from nailgun.openstack.common import jsonutils
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks
from nailgun.test.base import reverse


class TestNodeCollectionNICsHandler(BaseIntegrationTest):

    def test_put_handler_with_one_node(self):
        cluster = self.env.create_cluster(api=True)
        mac = self.env.generate_random_mac()
        meta = {}
        self.env.set_interfaces_in_meta(meta, [
            {'name': 'eth0', 'mac': mac},
            {'name': 'eth1', 'mac': self.env.generate_random_mac()}])
        node = self.env.create_node(api=True, meta=meta, mac=mac,
                                    cluster_id=cluster['id'])

        resp_get = self.app.get(
            reverse('NodeNICsHandler', kwargs={'node_id': node['id']}),
            headers=self.default_headers)
        self.assertEqual(resp_get.status_code, 200)

        a_nets = filter(lambda nic: nic['mac'] == mac,
                        resp_get.json_body)[0]['assigned_networks']
        for resp_nic in resp_get.json_body:
            if resp_nic['mac'] == mac:
                resp_nic['assigned_networks'] = []
            else:
                resp_nic['assigned_networks'].extend(a_nets)
                resp_nic['assigned_networks'].sort()
        nodes_list = [{'id': node['id'], 'interfaces': resp_get.json_body}]

        resp_put = self.app.put(
            reverse('NodeCollectionNICsHandler'),
            jsonutils.dumps(nodes_list),
            headers=self.default_headers)
        self.assertEqual(resp_put.status_code, 200)
        self.assertEqual(resp_put.json_body, nodes_list)

    @fake_tasks()
    def test_interface_changes_added(self):
        # Creating cluster with node
        self.env.create_cluster()
        cluster = self.env.clusters[0]
        self.env.create_node(
            roles=['controller'],
            pending_addition=True,
            cluster_id=cluster.id
        )
        # Deploying cluster
        deployment_task = self.env.launch_deployment()
        self.env.wait_ready(deployment_task)

        def filter_changes(chg_type, chg_list):
            return filter(lambda x: x.get('name') == chg_type, chg_list)

        # cluster = self.env.clusters[0]
        changes = filter_changes(
            consts.CLUSTER_CHANGES.interfaces,
            cluster['changes']
        )
        # Checking no interfaces change after cluster deployed
        self.assertEquals(0, len(changes))

        node_id = self.env.nodes[0].id
        # Getting nics
        resp = self.env.node_nics_get(node_id)

        # Updating nics
        self.env.node_nics_put(node_id, resp.json_body)
        # Checking 'interfaces' change in cluster changes
        changes = filter_changes(
            consts.CLUSTER_CHANGES.interfaces,
            cluster['changes']
        )
        self.assertEquals(1, len(changes))


class TestNodeCollectionNICsDefaultHandler(BaseIntegrationTest):

    def setUp(self):
        super(TestNodeCollectionNICsDefaultHandler, self).setUp()

        # two nodes in one cluster
        self.cluster = self.env.create(
            nodes_kwargs=[
                {'roles': ['controller'], 'mac': '01:01:01:01:01:01'},
                {'roles': ['compute'], 'mac': '02:02:02:02:02:02'}])

        # one node in another cluster
        self.env.create(
            nodes_kwargs=[
                {'roles': ['controller'], 'mac': '03:03:03:03:03:03'}])

        # one node outside clusters
        self.env.create_node(api=True, mac='04:04:04:04:04:04')

    def test_get_w_cluster_id(self):
        # get nics of cluster and check that response is ok
        resp = self.app.get(
            '{url}?cluster_id={cluster_id}'.format(
                url=reverse('NodeCollectionNICsDefaultHandler'),
                cluster_id=self.cluster['id']),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)

        # check response
        self.assertEqual(len(resp.json_body), 2)

        macs = [iface['mac'] for node in resp.json_body for iface in node]
        self.assertTrue('01:01:01:01:01:01' in macs)
        self.assertTrue('02:02:02:02:02:02' in macs)
        self.assertFalse('03:03:03:03:03:03' in macs)

    def test_get_wo_cluster_id(self):
        # get nics of cluster and check that response is ok
        resp = self.app.get(
            reverse('NodeCollectionNICsDefaultHandler'),
            headers=self.default_headers)
        self.assertEqual(resp.status_code, 200)

        # check response
        self.assertEqual(len(resp.json_body), 3)

        macs = [iface['mac'] for node in resp.json_body for iface in node]
        self.assertTrue('01:01:01:01:01:01' in macs)
        self.assertTrue('02:02:02:02:02:02' in macs)
        self.assertTrue('03:03:03:03:03:03' in macs)
