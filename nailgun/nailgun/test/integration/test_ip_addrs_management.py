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


from oslo_serialization import jsonutils

from nailgun import consts
from nailgun.db.sqlalchemy.models import IPAddr
from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun import objects
from nailgun.utils import reverse

from nailgun.test.base import BaseIntegrationTest


class BaseIPAddrTest(BaseIntegrationTest):

    __test__ = False

    def setUp(self):
        self.maxDiff = None
        super(BaseIPAddrTest, self).setUp()
        self.cluster = self.env.create(
            release_kwargs={'version': '1111-8.0'},
            cluster_kwargs={'api': False}
        )

        net_manager = objects.Cluster.get_network_manager(self.cluster)
        self.management_net = net_manager.get_network_by_netname(
            consts.NETWORKS.management, self.cluster.network_groups
        )
        self.management_vips = self.db.query(IPAddr).filter(
            IPAddr.vip_name.isnot(None),
            IPAddr.network == self.management_net.id
        ).all()
        self.vip_ids = [v.id for v in self.management_vips]

        self.expected_vips = [
            {
                'vip_name': 'vrouter',
                'node': None,
                'ip_addr': '192.168.0.1',
                'is_user_defined': False,
                'vip_namespace': 'vrouter'
            },
            {
                'vip_name': 'management',
                'node': None,
                'ip_addr': '192.168.0.2',
                'is_user_defined': False,
                'vip_namespace': 'haproxy'
            },
            {
                'ip_addr': '172.16.0.3',
                'is_user_defined': False,
                'node': None,
                'vip_name': 'public',
                'vip_namespace': 'haproxy'
            },
            {
                'ip_addr': '172.16.0.2',
                'is_user_defined': False,
                'node': None,
                'vip_name': 'vrouter_pub',
                'vip_namespace': 'vrouter'
            },

        ]
        self.non_existing_id = 11341134

    def _remove_from_response(self, response, fields):
        list_given = isinstance(response, list)
        if not list_given:
            response = [response]

        clean_response = []
        for resp_item in response:
            resp_item_clone = resp_item.copy()
            for f in fields:
                resp_item_clone.pop(f, None)
            clean_response.append(resp_item_clone)

        return clean_response if list_given else clean_response[0]

    def _check_ip_intersection(self, ip_addr):
        handlers_info = {
            'ClusterVIPHandler': {
                'patch_kwargs': {
                    'cluster_id': self.cluster['id'],
                    'ip_addr_id': self.management_vips[0].id
                },
                'patch_data': {
                    'is_user_defined': True,
                    'ip_addr': ip_addr,
                    'vip_namespace': 'new-namespace'
                },
            },
            'ClusterVIPCollectionHandler': {
                'patch_kwargs': {'cluster_id': self.cluster['id']},
                'patch_data': [
                    {
                        'id': self.management_vips[0].id,
                        'ip_addr': ip_addr,
                        'is_user_defined': True
                    }
                ]
            }
        }

        resp = self.app.patch(
            reverse(
                self.handler_name,
                kwargs=handlers_info[self.handler_name]['patch_kwargs'],
            ),
            params=jsonutils.dumps(
                handlers_info[self.handler_name]['patch_data']),
            headers=self.default_headers,
            expect_errors=True
        )

        self.assertEqual(resp.status_code, 409)

        net_group = self.db.query(NetworkGroup)\
            .filter_by(id=self.management_vips[0].network)\
            .first()

        err_msg = (
            "IP address {0} is already allocated within "
            "{1} network with CIDR {2}"
            .format(ip_addr, net_group.name, net_group.cidr)
        )
        self.assertIn(err_msg, resp.json_body['message'])

    def test_update_user_defined_fail_if_ip_addr_intersection(self):
        intersecting_vip = self.management_vips[1].ip_addr
        self._check_ip_intersection(intersecting_vip)

    def check_create_vip(self, create_data=None):
        data = {
            'ip_addr': "192.168.0.15",
            'network': self.management_net.id,
            'vip_name': 'management',
        }

        if create_data:
            data.update(create_data)

        resp = self.app.post(
            reverse(
                'ClusterVIPCollectionHandler',
                kwargs={'cluster_id': self.cluster['id']}
            ),
            params=jsonutils.dumps(data),
            headers=self.default_headers
        )

        self.assertEqual(resp.status_code, 200)

        return resp

    def check_vip_removed(self, vip_id):
        vip_db = self.db.query(objects.IPAddr.model)\
            .filter_by(id=vip_id).first()
        self.assertIsNone(vip_db)


class TestIPAddrList(BaseIPAddrTest):

    __test__ = True

    handler_name = 'ClusterVIPCollectionHandler'

    def test_create_vip_for_cluster(self):
        create_data = {
            'is_user_defined': True
        }

        self.check_create_vip(create_data)

    def test_create_vip_for_cluster_wo_is_user_defined_flag(self):
        create_resp = self.check_create_vip()

        get_resp = self.app.get(
            reverse(
                'ClusterVIPHandler',
                kwargs={
                    'cluster_id': self.cluster['id'],
                    'ip_addr_id': create_resp.json_body['id']
                }
            ),
            headers=self.default_headers
        )

        self.assertTrue(get_resp.json_body['is_user_defined'])

    def test_vips_with_unset_is_user_defined_are_removed(self):
        vip_one = self.check_create_vip(
            {'vip_name': 'management', 'ip_addr': '192.168.17.17'}
        ).json_body
        vip_two = self.check_create_vip(
            {'vip_name': 'vrouter', 'ip_addr': '192.168.17.18'}
        ).json_body

        update_data = [
            {'id': vip_one['id']},
            {'id': vip_two['id'], 'is_user_defined': False}
        ]

        resp = self.app.patch(
            reverse(
                self.handler_name,
                kwargs={
                    'cluster_id': self.cluster['id']
                }
            ),
            params=jsonutils.dumps(update_data),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)

        # check that only one VIP is present in the response
        self.assertEqual(len(resp.json_body), 1)
        self.assertEqual(resp.json_body[0]['id'], vip_one['id'])

        self.check_vip_removed(vip_two['id'])

    def test_empty_response_if_all_vips_removed(self):
        vip = self.check_create_vip().json_body

        update_data = [{'id': vip['id'], 'is_user_defined': False}]

        resp = self.app.patch(
            reverse(
                self.handler_name,
                kwargs={
                    'cluster_id': self.cluster['id']
                }
            ),
            params=jsonutils.dumps(update_data),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        self.assertEqual(resp.json_body, {})

        self.check_vip_removed(vip['id'])

    def test_vips_list_for_cluster(self):
        resp = self.app.get(
            reverse(
                self.handler_name,
                kwargs={'cluster_id': self.cluster['id']}
            ),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        self.assertItemsEqual(
            self.expected_vips,
            self._remove_from_response(
                resp.json_body,
                ['id', 'network']
            ),
        )

    def test_vips_list_with_two_clusters(self):
        self.second_cluster = self.env.create_cluster(api=False)
        self.env.create_ip_addrs_by_rules(
            self.second_cluster,
            {
                'management': {
                    'haproxy': '192.168.0.1',
                    'vrouter': '192.168.0.2',
                }
            }
        )
        resp = self.app.get(
            reverse(
                self.handler_name,
                kwargs={'cluster_id': self.cluster['id']}
            ),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        self.assertItemsEqual(
            self.expected_vips,
            self._remove_from_response(
                resp.json_body,
                ['id', 'network']
            ),
        )

    def test_wrong_cluster(self):
        resp = self.app.get(
            reverse(
                self.handler_name,
                kwargs={'cluster_id': 99999}
            ),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(404, resp.status_code)

    def test_update(self):
        update_data = [
            {
                'id': self.vip_ids[0],
                'is_user_defined': True,
                'ip_addr': '192.168.0.44'
            },
            {
                'id': self.vip_ids[1],
                'ip_addr': '192.168.0.43'
            }
        ]
        expected_data = [
            {
                'id': self.vip_ids[0],
                'is_user_defined': True,
                'vip_name': self.management_vips[0]["vip_name"],
                'ip_addr': '192.168.0.44',
                'vip_namespace': 'vrouter'
            },
            {
                'id': self.vip_ids[1],
                'is_user_defined': False,
                'vip_name': self.management_vips[1]["vip_name"],
                'ip_addr': '192.168.0.43',
                'vip_namespace': 'haproxy'
            }
        ]
        resp = self.app.patch(
            reverse(
                self.handler_name,
                kwargs={
                    'cluster_id': self.cluster['id']
                }
            ),
            params=jsonutils.dumps(update_data),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)

        self.assertEqual(expected_data, self._remove_from_response(
            resp.json_body,
            ['node', 'network']
        ))

    def test_update_fail_with_no_id(self):
        new_data = [{
            'ip_addr': '192.168.0.44'
        }]
        resp = self.app.patch(
            reverse(
                self.handler_name,
                kwargs={
                    'cluster_id': self.cluster['id']
                }
            ),
            params=jsonutils.dumps(new_data),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(400, resp.status_code)
        self.assertIn("'id' is a required property", resp.json_body["message"])

    def test_update_fail_with_non_updatable_field(self):
        new_data = [
            {
                'id': self.vip_ids[0],
                'ip_addr': '192.168.0.44'
            },
            {
                'id': self.vip_ids[1],
                'ip_addr': '192.168.0.44',
                'network': self.non_existing_id
            }
        ]
        resp = self.app.patch(
            reverse(
                self.handler_name,
                kwargs={
                    'cluster_id': self.cluster['id']
                }
            ),
            params=jsonutils.dumps(new_data),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(400, resp.status_code)
        self.assertIn("'network'", resp.json_body["message"])

    def test_update_pass_with_non_updatable_not_changed_field(self):
        new_data = [
            {
                'id': self.management_vips[0].id,
                'ip_addr': '192.168.0.44',
                'network': self.management_vips[0].network
            }
        ]
        resp = self.app.patch(
            reverse(
                self.handler_name,
                kwargs={
                    'cluster_id': self.cluster['id']
                }
            ),
            params=jsonutils.dumps(new_data),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(200, resp.status_code)

    def test_update_fail_with_not_found_id(self):
        new_data = [{
            'id': self.non_existing_id,
            'ip_addr': '192.168.0.44'
        }]
        resp = self.app.patch(
            reverse(
                self.handler_name,
                kwargs={
                    'cluster_id': self.cluster['id']
                }
            ),
            params=jsonutils.dumps(new_data),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertIn(str(self.non_existing_id), resp.json_body["message"])
        self.assertEqual(400, resp.status_code)

    def test_update_fail_on_dict_request(self):
        new_data = {
            'id': self.vip_ids[0],
            'ip_addr': '192.168.0.44'
        }
        resp = self.app.patch(
            reverse(
                self.handler_name,
                kwargs={
                    'cluster_id': self.cluster['id']
                }
            ),
            params=jsonutils.dumps(new_data),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(400, resp.status_code)

    def test_update_failing_on_empty_request(self):
        resp = self.app.patch(
            reverse(
                self.handler_name,
                kwargs={
                    'cluster_id': self.cluster['id']
                }
            ),
            params="",
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(400, resp.status_code)

    def test_update_not_failing_on_empty_list_request(self):
        resp = self.app.patch(
            reverse(
                self.handler_name,
                kwargs={
                    'cluster_id': self.cluster['id']
                }
            ),
            params=jsonutils.dumps([]),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(200, resp.status_code)

    def test_update_fail_on_wrong_fields(self):
        new_data_suites = [
            [{
                'id': self.vip_ids[0],
                "network": self.non_existing_id,
                "wrong_field": "value"
            }]
        ]
        for new_data in new_data_suites:
            resp = self.app.patch(
                reverse(
                    self.handler_name,
                    kwargs={
                        'cluster_id': self.cluster['id']
                    }
                ),
                params=jsonutils.dumps(new_data),
                headers=self.default_headers,
                expect_errors=True
            )
            self.assertEqual(400, resp.status_code)

    def test_update_fail_on_ip_from_wrong_cluster(self):
        another_cluster = self.env.create_cluster(api=False)
        new_data_suites = [
            [{
                'id': self.vip_ids[0],
                "network": self.non_existing_id
            }]
        ]
        for new_data in new_data_suites:
            resp = self.app.patch(
                reverse(
                    self.handler_name,
                    kwargs={
                        'cluster_id': another_cluster['id']
                    }
                ),
                params=jsonutils.dumps(new_data),
                headers=self.default_headers,
                expect_errors=True
            )
            self.assertEqual(400, resp.status_code)
            self.assertIn(
                "does not belong to cluster",
                resp.json_body.get("message")
            )

    def test_all_data_not_changed_on_single_error(self):
        old_all_addr = [dict(a) for a in self.db.query(IPAddr).all()]
        self.db.commit()  # we will re-query all from ip_addr table later
        new_data = [
            {
                'id': self.vip_ids[0],
                'is_user_defined': True,
                'ip_addr': '192.168.0.44'
            },
            {
                # should fail on no id
                'is_user_defined': False,
                'ip_addr': '192.168.0.43'
            }
        ]
        resp = self.app.patch(
            reverse(
                self.handler_name,
                kwargs={
                    'cluster_id': self.cluster['id']
                }
            ),
            params=jsonutils.dumps(new_data),
            headers=self.default_headers,
            expect_errors=True
        )
        new_all_addr = [dict(a) for a in self.db.query(IPAddr).all()]
        self.assertEqual(old_all_addr, new_all_addr)
        self.assertEqual(400, resp.status_code)

    def test_ipaddr_filter_by_network_id(self):
        resp = self.app.get(
            reverse(
                self.handler_name,
                kwargs={
                    'cluster_id': self.cluster['id']
                }
            ),
            params={"network_id": self.management_vips[0]['network']},
            headers=self.default_headers
        )
        self.assertEqual([dict(v) for v in self.management_vips],
                         resp.json_body)
        self.assertEqual(200, resp.status_code)

    def test_ipaddr_filter_by_missing_network_id(self):
        resp = self.app.get(
            reverse(
                self.handler_name,
                kwargs={
                    'cluster_id': self.cluster['id']
                }
            ),
            params={"network_id": self.non_existing_id},
            headers=self.default_headers
        )
        self.assertEqual([], resp.json_body)
        self.assertEqual(200, resp.status_code)

    def test_ipaddr_filter_by_network_role(self):
        public_net_vip_names = ('vrouter_pub', 'public')

        resp = self.app.get(
            reverse(
                self.handler_name,
                kwargs={
                    'cluster_id': self.cluster['id']
                }
            ),
            params={'network_role': 'public/vip'},
            headers=self.default_headers
        )

        expected_vips = [vip for vip in self.expected_vips
                         if vip['vip_name'] in public_net_vip_names]
        self.assertItemsEqual(
            expected_vips,
            self._remove_from_response(
                resp.json_body,
                ['id', 'network']
            )
        )
        self.assertEqual(200, resp.status_code)

    def test_ipaddr_filter_by_missing_network_role(self):
        resp = self.app.get(
            reverse(
                self.handler_name,
                kwargs={
                    'cluster_id': self.cluster['id']
                }
            ),
            params={'network_role': 'NOT_EXISTING_NETWORK_ROLE'},
            headers=self.default_headers
        )
        self.assertEqual([], resp.json_body)
        self.assertEqual(200, resp.status_code)


class TestIPAddrHandler(BaseIPAddrTest):

    __test__ = True

    handler_name = 'ClusterVIPHandler'

    def test_get_ip_addr(self):
        resp = self.app.get(
            reverse(
                self.handler_name,
                kwargs={
                    'cluster_id': self.cluster['id'],
                    'ip_addr_id': self.vip_ids[0]
                }
            ),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        self.assertIn(
            self._remove_from_response(
                resp.json_body,
                ['id', 'network']
            ),
            self.expected_vips
        )

    def test_delete_fail(self):
        resp = self.app.delete(
            reverse(
                self.handler_name,
                kwargs={
                    'cluster_id': self.cluster['id'],
                    'ip_addr_id': self.vip_ids[0]
                }
            ),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(405, resp.status_code)

    def test_fail_on_no_vip_metadata(self):
        not_vip_ip_addr = IPAddr(
            network=self.cluster.network_groups[0].id,
            ip_addr="127.0.0.1",
            vip_name=None
        )
        self.db.add(not_vip_ip_addr)
        self.db.flush()
        not_vip_id = not_vip_ip_addr.get('id')

        resp = self.app.get(
            reverse(
                self.handler_name,
                kwargs={
                    'cluster_id': self.cluster['id'],
                    'ip_addr_id': not_vip_id
                }
            ),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(400, resp.status_code)

    def test_update_ip_addr(self):
        update_data = {
            'is_user_defined': True,
            'ip_addr': '192.168.0.100',
            'vip_namespace': 'new-namespace'
        }
        expected_data = {
            'is_user_defined': True,
            'vip_name': self.management_vips[0]['vip_name'],
            'ip_addr': '192.168.0.100',
            'vip_namespace': 'new-namespace'
        }
        resp = self.app.patch(
            reverse(
                self.handler_name,
                kwargs={
                    'cluster_id': self.cluster['id'],
                    'ip_addr_id': self.management_vips[0]['id']
                }
            ),
            params=jsonutils.dumps(update_data),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        self.assertEqual(
            expected_data,
            self._remove_from_response(
                resp.json_body,
                ['id', 'network', 'node']
            )
        )

    def test_update_ip_addr_with_put(self):
        update_data = {
            'is_user_defined': True,
            'ip_addr': '192.168.0.100',
            'vip_namespace': 'new-namespace'
        }
        expected_data = {
            'is_user_defined': True,
            'vip_name': self.management_vips[0]['vip_name'],
            'ip_addr': '192.168.0.100',
            'vip_namespace': 'new-namespace'
        }
        resp = self.app.put(
            reverse(
                self.handler_name,
                kwargs={
                    'cluster_id': self.cluster['id'],
                    'ip_addr_id': self.management_vips[0]['id']
                }
            ),
            params=jsonutils.dumps(update_data),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        self.assertEqual(
            expected_data,
            self._remove_from_response(
                resp.json_body,
                ['id', 'network', 'node']
            )
        )

    def test_vip_namespase_update(self):
        changed_vip = self.management_vips[0]

        update_data = {
            'is_user_defined': True,
            'ip_addr': '192.168.0.100',
            'vip_namespace': 'new-namespace',
        }

        resp = self.app.patch(
            reverse(
                self.handler_name,
                kwargs={
                    'cluster_id': self.cluster['id'],
                    'ip_addr_id': changed_vip['id']
                }
            ),
            params=jsonutils.dumps(update_data),
            headers=self.default_headers
        )

        resp = self.env.neutron_networks_get(self.cluster.id)
        net_conf = resp.json_body

        self.assertIn(changed_vip['vip_name'], net_conf['vips'])

        vip = net_conf['vips'][changed_vip['vip_name']]
        self.assertEqual(vip['namespace'], update_data['vip_namespace'])

    def test_vip_update_remove_if_user_defined_set_to_false(self):
        create_resp = self.check_create_vip()

        update_data = {
            'is_user_defined': False
        }

        change_resp = self.app.put(
            reverse(
                self.handler_name,
                kwargs={'ip_addr_id': create_resp.json_body['id'],
                        'cluster_id': self.cluster['id']}
            ),
            headers=self.default_headers,
            params=jsonutils.dumps(update_data)
        )

        self.assertEqual(change_resp.status_code, 200)
        self.assertEqual(change_resp.json_body, {})
        self.check_vip_removed(create_resp.json_body['id'])
