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

from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import reverse


class TestHandlers(BaseIntegrationTest):

    def test_put_handler_with_one_node(self):
        cluster = self.env.create_cluster(api=True)
        mac = self.env.generate_random_mac()
        meta = {}
        self.env.set_interfaces_in_meta(meta, [
            {'name': 'eth0', 'mac': mac},
            {'name': 'eth1', 'mac': self.env.generate_random_mac()}])
        node = self.env.create_node(api=True, meta=meta, mac=mac,
                                    cluster_id=cluster['id'])

        resp = self.app.get(
            reverse('NodeNICsHandler', kwargs={'node_id': node['id']}),
            headers=self.default_headers)
        self.assertEquals(resp.status_code, 200)
        response = json.loads(resp.body)
        a_nets = filter(lambda nic: nic['mac'] == mac,
                        response)[0]['assigned_networks']
        for resp_nic in response:
            if resp_nic['mac'] == mac:
                resp_nic['assigned_networks'] = []
            else:
                resp_nic['assigned_networks'].extend(a_nets)
                resp_nic['assigned_networks'].sort()
        nodes_list = [{'id': node['id'], 'interfaces': response}]

        resp = self.app.put(
            reverse('NodeCollectionNICsHandler'),
            json.dumps(nodes_list),
            headers=self.default_headers)
        self.assertEquals(resp.status_code, 200)
        new_response = json.loads(resp.body)
        self.assertEquals(new_response, nodes_list)

    def test_interface_changes_added(self):
        # Creating cluster with node
        self.env.create(
            cluster_kwargs={
                'name': 'test_name'
            },
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True}
            ]
        )

        def filter_changes(chg_type, chns):
            return filter(lambda x: x.get('name') == chg_type, chns)

        cluster = self.env.clusters[0]
        changes = filter_changes('interfaces', cluster['changes'])
        changes_len = len(changes)
        self.assertEquals(0, changes_len)
        node_id = self.env.nodes[0].id
        # Getting nics
        resp = self.env.node_nics_get(node_id)
        interfaces = json.loads(resp.body)
        # Updating nics
        self.env.node_nics_put(node_id, interfaces)
        # Checking 'interfaces' change in cluster changes
        new_changes = filter_changes('interfaces', cluster['changes'])
        self.assertEquals(changes_len + 1, len(new_changes))
