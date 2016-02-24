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

import yaml

from oslo_serialization import jsonutils

from nailgun.db.sqlalchemy.models import NodeBondInterface

from nailgun import consts
from nailgun.test.base import BaseIntegrationTest
from nailgun.utils import reverse


class TestAssignmentHandlers(BaseIntegrationTest):
    def _assign_roles(self, assignment_data, expect_errors=False):
        return self.app.post(
            reverse(
                'NodeAssignmentHandler',
                kwargs={'cluster_id': self.cluster.id}
            ),
            jsonutils.dumps(assignment_data),
            headers=self.default_headers,
            expect_errors=expect_errors
        )

    def test_assignment(self):
        self.env.create(
            cluster_kwargs={"api": True},
            nodes_kwargs=[
                {
                    "cluster_id": None,
                    "api": True
                }
            ]
        )
        self.cluster = self.env.clusters[0]
        node = self.env.nodes[0]
        assignment_data = [
            {
                "id": node.id,
                "roles": ['controller']
            }
        ]
        resp = self._assign_roles(assignment_data)
        self.assertEqual(200, resp.status_code)
        self.assertEqual(node.cluster, self.cluster)
        self.datadiff(
            node.pending_roles,
            assignment_data[0]["roles"]
        )

        resp = self._assign_roles(assignment_data, True)
        self.assertEqual(400, resp.status_code)

    def test_unassignment(self):
        cluster = self.env.create(
            cluster_kwargs={"api": True},
            nodes_kwargs=[{}]
        )
        node = self.env.nodes[0]
        # correct unassignment
        resp = self.app.post(
            reverse(
                'NodeUnassignmentHandler',
                kwargs={'cluster_id': cluster['id']}
            ),
            jsonutils.dumps([{'id': node.id}]),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        self.assertIsNone(node.cluster)
        self.assertEqual(node.pending_roles, [])

        # Test with invalid node ids
        for node_id in (0, node.id + 50):
            resp = self.app.post(
                reverse(
                    'NodeUnassignmentHandler',
                    kwargs={'cluster_id': cluster['id']}
                ),
                jsonutils.dumps([{'id': node_id}]),
                headers=self.default_headers,
                expect_errors=True
            )
            self.assertEqual(400, resp.status_code)
        # Test with invalid cluster id
        resp = self.app.post(
            reverse(
                'NodeUnassignmentHandler',
                kwargs={'cluster_id': cluster['id'] + 5}
            ),
            jsonutils.dumps([{'id': node.id}]),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 404)

        # Test with wrong cluster id
        self.env.create(
            cluster_kwargs={"api": True},
            nodes_kwargs=[{}]
        )

        resp = self.app.post(
            reverse(
                'NodeUnassignmentHandler',
                kwargs={'cluster_id': cluster['id']}
            ),
            jsonutils.dumps([{'id': self.env.clusters[1].nodes[0].id}]),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(resp.status_code, 400)

    def test_unassignment_after_deploy(self):
        cluster = self.env.create(
            nodes_kwargs=[{}]
        )
        node = self.env.nodes[0]
        node.status = 'error'
        self.db.commit()
        resp = self.app.post(
            reverse(
                'NodeUnassignmentHandler',
                kwargs={'cluster_id': cluster['id']}
            ),
            jsonutils.dumps([{'id': node.id}]),
            headers=self.default_headers
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(node.pending_deletion, True)

    def test_assigment_with_invalid_cluster(self):
        node = self.env.create_node(api=False)

        resp = self.app.post(
            reverse(
                'NodeAssignmentHandler',
                kwargs={'cluster_id': '9999'}
            ),
            jsonutils.dumps([{
                'id': node.id,
                'roles': ['controller']
            }]),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEquals(404, resp.status_code)

    def test_assign_conflicting_roles(self):
        self.env.create(
            cluster_kwargs={"api": True},
            nodes_kwargs=[
                {
                    "cluster_id": None,
                    "api": True
                }
            ]
        )
        self.cluster = self.env.clusters[0]
        node = self.env.nodes[0]
        assignment_data = [
            {
                "id": node.id,
                "roles": ['controller', 'compute']
            }
        ]
        resp = self._assign_roles(assignment_data, True)
        self.assertEquals(400, resp.status_code)

    def test_assign_conflicting_all_role(self):
        ROLE = yaml.safe_load("""
            name: test_role
            meta:
              name: "Some plugin role"
              description: "Some description"
              conflicts: "*"
            volumes_roles_mapping:
                - id: os
                  allocate_size: all
        """)

        release = self.env.create_release()
        resp = self.env.create_role(release.id, ROLE)

        self.env.create(
            cluster_kwargs={
                "api": True,
                "release_id": release.id
            },
            nodes_kwargs=[
                {
                    "cluster_id": None,
                    "api": True
                }
            ]
        )
        self.cluster = self.env.clusters[0]
        node = self.env.nodes[0]
        assignment_data = [
            {
                "id": node.id,
                "roles": ['controller', 'test_role']
            }
        ]
        resp = self._assign_roles(assignment_data, True)
        self.assertEquals(400, resp.status_code, resp.body)

        assignment_data[0]["roles"] = ['test_role']
        resp = self._assign_roles(assignment_data)
        self.assertEquals(200, resp.status_code, resp.body)

    def test_add_node_with_cluster_network_template(self):
        net_template = {
            "adv_net_template": {
                "default": {
                    "network_assignments": {
                        "management": {
                            "ep": "br-mgmt"
                        },
                        "storage": {
                            "ep": "br-storage"
                        },
                        "public": {
                            "ep": "br-ex"
                        },
                        "private": {
                            "ep": "br-prv"
                        },
                        "fuelweb_admin": {
                            "ep": "br-fw-admin"
                        }
                    },
                    "templates_for_node_role": {
                        "controller": [
                            "common"
                        ]
                    },
                    "nic_mapping": {
                        "default": {
                            "if4": "eth3",
                            "if1": "eth0",
                            "if2": "eth1",
                            "if3": "eth2"
                        }
                    },
                    "network_scheme": {
                        "common": {
                            "endpoints": [
                                "br-mgmt"
                            ],
                            "transformations": [
                                {
                                    "action": "add-br",
                                    "name": "br-mgmt"
                                },
                                {
                                    "action": "add-port",
                                    "bridge": "br-mgmt",
                                    "name": "<% if2 %>"
                                }
                            ],
                            "roles": {
                                "management": "br-mgmt"
                            }
                        }
                    }
                }
            }
        }

        cluster = self.env.create_cluster(
            api=False,
            net_provider=consts.CLUSTER_NET_PROVIDERS.neutron
        )
        cluster.release.version = '1111-7.0'
        cluster.network_config.configuration_template = net_template

        node = self.env.create_node()
        assignment_data = [
            {
                "id": node.id,
                "roles": ['controller']
            }
        ]
        self.app.post(
            reverse(
                'NodeAssignmentHandler',
                kwargs={'cluster_id': cluster.id}
            ),
            jsonutils.dumps(assignment_data),
            headers=self.default_headers
        )
        net_scheme = node.network_template['templates']['common']
        self.assertNotEqual({}, node.network_template)
        self.assertEquals(['br-mgmt'], net_scheme['endpoints'])
        self.assertEquals({'management': 'br-mgmt'}, net_scheme['roles'])

        # The order of transformations matters
        self.assertIn('add-br', net_scheme['transformations'][0].values())
        self.assertIn('add-port', net_scheme['transformations'][1].values())
        self.assertEquals('eth1', net_scheme['transformations'][1]['name'])


class TestClusterStateUnassignment(BaseIntegrationTest):

    def test_delete_bond_and_networks_state_on_unassignment(self):
        """Test verifies that

        1. bond configuration will be deleted
        2. network unassigned from node interfaces
        when node unnasigned from cluster
        """
        cluster = self.env.create(
            nodes_kwargs=[{}]
        )
        node = self.env.nodes[0]
        node.bond_interfaces.append(
            NodeBondInterface(name='ovs-bond0',
                              slaves=node.nic_interfaces))
        self.db.flush()
        resp = self.app.post(
            reverse(
                'NodeUnassignmentHandler',
                kwargs={'cluster_id': cluster['id']}
            ),
            jsonutils.dumps([{'id': node.id}]),
            headers=self.default_headers
        )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(node.bond_interfaces, [])
        for interface in node.interfaces:
            self.assertEqual(interface.assigned_networks_list, [])
