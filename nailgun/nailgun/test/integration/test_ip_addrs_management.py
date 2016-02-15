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
import six

from nailgun import consts
from nailgun.db.sqlalchemy.models import IPAddr
from nailgun.db.sqlalchemy.models import NetworkGroup
from nailgun import objects
from nailgun.test import base
from nailgun.test.integration.test_network_manager import \
    BaseNetworkManagerTest
from nailgun.utils import reverse


class BaseIPAddrTest(BaseNetworkManagerTest):

    __test__ = False

    def setUp(self):
        self.maxDiff = None
        super(BaseIPAddrTest, self).setUp()
        self.vips_to_create = {
            'management': {
                'haproxy': '192.168.0.1',
                'vrouter': '192.168.0.2',
            }
        }
        self.cluster = self.env.create_cluster(api=False)
        self.vips = self._create_ip_addrs_by_rules(
            self.cluster,
            self.vips_to_create)
        self.vip_ids = [v.get('id') for v in self.vips]
        self.expected_vips = [
            {
                'vip_name': 'haproxy',
                'node': None,
                'ip_addr': '192.168.0.1',
                'is_user_defined': False,
                'vip_namespace': None
            },
            {
                'vip_name': 'vrouter',
                'node': None,
                'ip_addr': '192.168.0.2',
                'is_user_defined': False,
                'vip_namespace': None
            }
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

    def _create_admin_ip(self):
        admin_netg = self.db.query(NetworkGroup).filter_by(
            name=consts.NETWORKS.fuelweb_admin
        ).first()

        ip_addr = IPAddr(ip_addr='10.20.0.3', network=admin_netg.id)
        self.db.add(ip_addr)
        self.db.flush()

        return ip_addr

    def _check_ip_intersection(self, ip_addr):
        handlers_info = {
            'ClusterVIPHandler': {
                'patch_kwargs': {
                    'cluster_id': self.cluster['id'],
                    'ip_addr_id': self.vips[0]['id']
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
                        'id': self.vip_ids[0],
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
            .filter_by(id=self.vips[0].network)\
            .first()

        err_msg = (
            "IP address {0} is already allocated within "
            "{1} network with CIDR {2}"
            .format(ip_addr, net_group.name, net_group.cidr)
        )
        self.assertIn(err_msg, resp.json_body['message'])

    def test_update_user_defined_fail_if_ip_addr_intersection(self):
        intersecting_vip = self.vips[1]['ip_addr']
        self._check_ip_intersection(intersecting_vip)


class TestIPAddrList(BaseIPAddrTest):

    __test__ = True

    handler_name = 'ClusterVIPCollectionHandler'

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
        self._create_ip_addrs_by_rules(
            self.second_cluster,
            self.vips_to_create
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

    def test_create_fail(self):
        resp = self.app.post(
            reverse(
                self.handler_name,
                kwargs={
                    'cluster_id': self.cluster['id'],
                    'ip_addr_id': self.vip_ids[0]
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
                'vip_name': self.vips[0]["vip_name"],
                'ip_addr': '192.168.0.44',
                'vip_namespace': None
            },
            {
                'id': self.vip_ids[1],
                'is_user_defined': False,
                'vip_name': self.vips[1]["vip_name"],
                'ip_addr': '192.168.0.43',
                'vip_namespace': None
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
                'id': self.vips[0].id,
                'ip_addr': '192.168.0.44',
                'network': self.vips[0].network
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
            params={"network_id": self.vips[0]['network']},
            headers=self.default_headers
        )
        self.assertEqual([dict(v) for v in self.vips], resp.json_body)
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

        # create more vips in another network
        ips_in_different_network_name = {
            'public': {
                'vrouter_pub': '172.16.0.4',
                'public': '172.16.0.5',
            }
        }
        expected_vips = self._create_ip_addrs_by_rules(
            self.cluster,
            ips_in_different_network_name)

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

        expected_vips = [dict(vip) for vip in expected_vips]
        self.assertItemsEqual(expected_vips, resp.json_body)
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
            'vip_name': self.vips[0]['vip_name'],
            'ip_addr': '192.168.0.100',
            'vip_namespace': 'new-namespace'
        }
        resp = self.app.patch(
            reverse(
                self.handler_name,
                kwargs={
                    'cluster_id': self.cluster['id'],
                    'ip_addr_id': self.vips[0]['id']
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
            'vip_name': self.vips[0]['vip_name'],
            'ip_addr': '192.168.0.100',
            'vip_namespace': 'new-namespace'
        }
        resp = self.app.put(
            reverse(
                self.handler_name,
                kwargs={
                    'cluster_id': self.cluster['id'],
                    'ip_addr_id': self.vips[0]['id']
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


class TestVIPReallocationOnTemplateChange(base.BaseIntegrationTest):

    def setUp(self):
        super(TestVIPReallocationOnTemplateChange, self).setUp()

        self.cluster = self.env.create(
            release_kwargs={'version': '1111-8.0'},
            cluster_kwargs={'api': False}
        )
        self.net_manager = objects.Cluster.get_network_manager(self.cluster)

        self.net_template = self.env.read_fixtures(['network_template_80'])[0]

        self.template_ndg_name = 'default'
        # use storage network endpoint
        self.template_net_end_point = 'br-storage'
        self.net_role = 'public/vip'

        # get vips and default network mapping for network role from
        # release network metadata
        self.vip_names, self.release_network = \
            self._get_vips_for_network_role()

        # set up new mapping for network role via template modification
        self.template_network = self.prepare_template()

    def _get_vips_for_network_role(self):
        vip_names = []
        network_metadata = self.cluster.release.network_roles_metadata
        for nr in network_metadata:
            if nr['id'] == self.net_role:
                vip_info = nr['properties']['vip']
                vip_names.extend([vi['name'] for vi in vip_info])
                network_mapping = nr['default_mapping']
        return vip_names, network_mapping

    def prepare_template(self):
        # add setup mapping between test network role and needed network
        ndg_data = \
            self.net_template['adv_net_template'][self.template_ndg_name]

        # following action will result in moving of VIPs for network role
        # to another network
        for net_name, scheme in six.iteritems(ndg_data['network_scheme']):
            if self.net_role in scheme['roles']:
                scheme['roles'][self.net_role] = \
                    self.template_net_end_point

        mapped_net = [
            net_name for net_name, ep_data
            in six.iteritems(ndg_data['network_assignments'])
            if ep_data['ep'] == self.template_net_end_point
        ][0]

        return mapped_net

    def check_vips(self, old_net, new_net, template):
        vips_before = self.net_manager.get_assigned_vips(self.cluster)

        self.assertEqual(set(self.vip_names),
                         set(six.iterkeys(vips_before[old_net])))

        objects.Cluster.set_network_template(self.cluster, template)

        vips_after = self.net_manager.get_assigned_vips(self.cluster)

        self.assertEqual(set(self.vip_names),
                         set(six.iterkeys(vips_after[new_net])))

    def test_vips_reallocated_when_template_is_set(self):
        self.net_manager.assign_vips_for_net_groups(self.cluster)
        self.check_vips(self.release_network, self.template_network,
                        self.net_template)

    def test_vips_reallocated_when_template_set_empty(self):
        objects.Cluster.set_network_template(self.cluster, self.net_template)
        self.check_vips(self.template_network, self.release_network, None)
