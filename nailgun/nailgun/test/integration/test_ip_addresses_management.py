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
from nailgun.test.integration.test_network_manager import \
    BaseNetworkManagerTest
from nailgun.utils import reverse


class BaseIPAddrTest(BaseNetworkManagerTest):
    def setUp(self):
        self.maxDiff = None
        super(BaseIPAddrTest, self).setUp()
        self.vips_to_create = {
            consts.NETWORKS.management: {
                consts.NETWORK_VIP_TYPES.haproxy: '192.168.0.1',
                consts.NETWORK_VIP_TYPES.vrouter: '192.168.0.2',
            },
            consts.NETWORKS.public: {
                consts.NETWORK_VIP_TYPES.haproxy: '172.16.0.2',
                consts.NETWORK_VIP_TYPES.vrouter: '172.16.0.3',
            },
        }
        self.cluster = self.env.create_cluster(api=False)
        self.vips = self._create_ip_addrs_by_rules(
            self.cluster,
            self.vips_to_create)
        self.vip_ids = [v.get('id') for v in self.vips]
        self.expected_vips = [
            {'vip_info': {'name': 'haproxy'}, 'node': None,
             'ip_addr': '172.16.0.2'},
            {'vip_info': {'name': 'vrouter'}, 'node': None,
             'ip_addr': '172.16.0.3'},
            {'vip_info': {'name': 'haproxy'}, 'node': None,
             'ip_addr': '192.168.0.1'},
            {'vip_info': {'name': 'vrouter'}, 'node': None,
             'ip_addr': '192.168.0.2'}
        ]

    def _remove_from_response(self, response, fields):
        list_given = isinstance(response, list)
        if not list_given:
            response = [response]

        clean_response = []
        for resp_item in response:
            resp_item_clone = dict(resp_item)
            for f in fields:
                resp_item_clone.pop(f, None)
            clean_response.append(resp_item_clone)

        return clean_response if list_given else clean_response[0]


class TestIPAddrList(BaseIPAddrTest):
    def test_vips_list_for_cluster(self):
        resp = self.app.get(
            reverse(
                'ClusterVIPCollectionHandler',
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
        self._create_ip_addrs_by_rules(
            self.second_cluster,
            self.vips_to_create
        )
        resp = self.app.get(
            reverse(
                'ClusterVIPCollectionHandler',
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
                'ClusterVIPCollectionHandler',
                kwargs={'cluster_id': 99999}
            ),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(404, resp.status_code)

    def test_create_fail(self):
        resp = self.app.post(
            reverse(
                'ClusterVIPCollectionHandler',
                kwargs={
                    'cluster_id': self.cluster['id'],
                    'ip_address_id': self.vip_ids[0]
                }
            ),
            {"some": "params"},
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(405, resp.status_code)

    def test_update(self):
        update_data = [
            {
                'id': self.vip_ids[0],
                'vip_info': {
                    'manual': True,
                    'name': "should-not-be-changed"
                },
                'ip_addr': '192.168.0.44'
            },
            {
                'id': self.vip_ids[1],
                'vip_info': {
                    'manual': False,
                    'name': "should-not-be-changed"
                },
                'ip_addr': '192.168.0.43'
            }
        ]
        expected_data = [
            {
                'id': self.vip_ids[0],
                'vip_info': {
                    'manual': True,
                    'name': self.vips[0].get("vip_info").get("name")
                },
                'ip_addr': '192.168.0.44'
            },
            {
                'id': self.vip_ids[1],
                'vip_info': {
                    'manual': False,
                    'name': self.vips[1].get("vip_info").get("name")
                },
                'ip_addr': '192.168.0.43'
            }
        ]
        resp = self.app.patch(
            reverse(
                'ClusterVIPCollectionHandler',
                kwargs={
                    'cluster_id': self.cluster['id']
                }
            ),
            params=jsonutils.dumps(update_data),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)

        self.assertListEqual(expected_data, self._remove_from_response(
            resp.json_body,
            ['node', 'network']
        ))

    def test_update_fail_with_no_id(self):
        new_data = [{
            'ip_addr': '192.168.0.44'
        }]
        resp = self.app.patch(
            reverse(
                'ClusterVIPCollectionHandler',
                kwargs={
                    'cluster_id': self.cluster['id']
                }
            ),
            params=jsonutils.dumps(new_data),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(400, resp.status_code)
        self.assertIn("192.168.0.44", resp.json_body["message"])

    def test_update_fail_with_not_found_id(self):
        new_data = [{
            'id': 1134,
            'ip_addr': '192.168.0.44'
        }]
        resp = self.app.patch(
            reverse(
                'ClusterVIPCollectionHandler',
                kwargs={
                    'cluster_id': self.cluster['id']
                }
            ),
            params=jsonutils.dumps(new_data),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(400, resp.status_code)
        self.assertIn("1134", resp.json_body["message"])

    def test_update_fail_on_dict_request(self):
        new_data = {
            'id': self.vip_ids[0],
            'ip_addr': '192.168.0.44'
        }
        resp = self.app.patch(
            reverse(
                'ClusterVIPCollectionHandler',
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
                'ClusterVIPCollectionHandler',
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
                'ClusterVIPCollectionHandler',
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
                "network": 1134,
                "wrong_field": "value"
            }]
        ]
        for new_data in new_data_suites:
            resp = self.app.patch(
                reverse(
                    'ClusterVIPCollectionHandler',
                    kwargs={
                        'cluster_id': self.cluster['id']
                    }
                ),
                params=jsonutils.dumps(new_data),
                headers=self.default_headers,
                expect_errors=True
            )
            self.assertEqual(400, resp.status_code)

    def test_all_data_not_chaned_on_single_error(self):
        old_all_addr = [dict(a) for a in self.db.query(IPAddr).all()]
        self.db.commit()  # we will re-query all from ip_addr table later
        new_data = [
            {
                'id': self.vip_ids[0],
                'vip_info': {
                    'manual': True
                },
                'ip_addr': '192.168.0.44'
            },
            {
                # should fail on no id
                'vip_info': {
                    'manual': False
                },
                'ip_addr': '192.168.0.43'
            }
        ]
        resp = self.app.patch(
            reverse(
                'ClusterVIPCollectionHandler',
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


class TestIPAddrHandler(BaseIPAddrTest):
    def test_get_ip_addr(self):
        resp = self.app.get(
            reverse(
                'ClusterVIPHandler',
                kwargs={
                    'cluster_id': self.cluster['id'],
                    'ip_address_id': self.vip_ids[0]
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
                'ClusterVIPHandler',
                kwargs={
                    'cluster_id': self.cluster['id'],
                    'ip_address_id': self.vip_ids[0]
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
            vip_info=None
        )
        self.db.add(not_vip_ip_addr)
        self.db.flush()
        not_vip_id = not_vip_ip_addr.get('id')

        resp = self.app.get(
            reverse(
                'ClusterVIPHandler',
                kwargs={
                    'cluster_id': self.cluster['id'],
                    'ip_address_id': not_vip_id
                }
            ),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(400, resp.status_code)

    def test_update_ip_addr(self):
        update_data = {
            'vip_info': {
                'manual': True
            },
            'ip_addr': '192.168.0.100'
        }
        expected_data = {
            'vip_info': {
                'manual': True,
                'name': 'vrouter'
            },
            'ip_addr': '192.168.0.100'
        }
        resp = self.app.patch(
            reverse(
                'ClusterVIPHandler',
                kwargs={
                    'cluster_id': self.cluster['id'],
                    'ip_address_id': self.vip_ids[0]
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

        resp = self.app.put(
            reverse(
                'ClusterVIPHandler',
                kwargs={
                    'cluster_id': self.cluster['id'],
                    'ip_address_id': self.vip_ids[0]
                }
            ),
            params=jsonutils.dumps(update_data),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
