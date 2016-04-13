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
from netaddr import IPNetwork
from oslo_serialization import jsonutils

from nailgun import consts
from nailgun.db.sqlalchemy import models
from nailgun import objects
from nailgun.test.base import BaseIntegrationTest
from nailgun.utils import reverse


class TestHandlers(BaseIntegrationTest):

    def setUp(self):
        super(TestHandlers, self).setUp()
        self.cluster = self.env.create_cluster(api=False)

    def test_create_network_group_w_cidr(self):
        resp = self.env._create_network_group()
        self.assertEqual(201, resp.status_code)
        ng_data = resp.json_body
        ng = objects.NetworkGroup.get_by_uid(ng_data['id'])
        self.assertEqual(len(ng.ip_ranges), 1)
        self.assertEqual(ng.ip_ranges[0].first, "10.3.0.2")
        self.assertEqual(ng.ip_ranges[0].last, "10.3.0.254")

    def test_create_network_group_w_ip_range(self):
        resp = self.env._create_network_group(
            meta={
                "notation": consts.NETWORK_NOTATION.ip_ranges,
                "ip_range": ["10.3.0.33", "10.3.0.158"]
            }
        )
        self.assertEqual(201, resp.status_code)
        ng_data = resp.json_body
        ng = objects.NetworkGroup.get_by_uid(ng_data['id'])
        self.assertEqual(len(ng.ip_ranges), 1)
        self.assertEqual(ng.ip_ranges[0].first, "10.3.0.33")
        self.assertEqual(ng.ip_ranges[0].last, "10.3.0.158")

    def test_create_network_group_wo_notation(self):
        resp = self.env._create_network_group(meta={"notation": None})
        self.assertEqual(201, resp.status_code)
        ng_data = resp.json_body
        ng = objects.NetworkGroup.get_by_uid(ng_data['id'])
        self.assertEqual(len(ng.ip_ranges), 0)

    def test_create_network_group_error(self):
        resp = self.env._create_network_group(
            meta={"notation": "new"},
            expect_errors=True
        )
        self.assertEqual(400, resp.status_code)
        self.assertEqual(
            resp.json_body["message"],
            "IPAddrRange object cannot be created for network "
            "'external' with notation='new', ip_range='None'")

        resp = self.env._create_network_group(
            meta={"notation": consts.NETWORK_NOTATION.ip_ranges},
            expect_errors=True
        )
        self.assertEqual(400, resp.status_code)
        self.assertEqual(resp.json_body["message"],
                         "IPAddrRange object cannot be created for network "
                         "'external' with notation='ip_ranges', "
                         "ip_range='None'")

        resp = self.env._create_network_group(
            meta={"notation": consts.NETWORK_NOTATION.ip_ranges,
                  "ip_range": ["10.3.0.33"]},
            expect_errors=True
        )
        self.assertEqual(400, resp.status_code)
        self.assertEqual(resp.json_body["message"],
                         "IPAddrRange object cannot be created for network "
                         "'external' with notation='ip_ranges', "
                         "ip_range='[u'10.3.0.33']'")

    def test_get_network_group(self):
        resp = self.env._create_network_group(name='test')
        self.assertEqual(201, resp.status_code)
        new_ng = resp.json_body

        net_group = resp.json_body

        resp = self.app.get(
            reverse(
                'NetworkGroupHandler',
                kwargs={'obj_id': net_group['id']}
            ),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        self.assertEqual(resp.json_body, new_ng)

    def test_delete_network_group(self):
        resp = self.env._create_network_group(name='test')
        self.assertEqual(201, resp.status_code)

        net_group = resp.json_body

        resp = self.app.delete(
            reverse(
                'NetworkGroupHandler',
                kwargs={'obj_id': net_group['id']}
            ),
            headers=self.default_headers
        )
        self.assertEqual(204, resp.status_code)

    def test_delete_network_group_cleanup_ip_range(self):
        ng_id = self.env._create_network_group(
            meta={
                "notation": "ip_ranges",
                "ip_range": ["10.3.0.33", "10.3.0.158"]
            }
        ).json["id"]
        self.app.delete(
            reverse(
                'NetworkGroupHandler',
                kwargs={'obj_id': ng_id}
            ),
            headers=self.default_headers,
        )
        ip_range = self.db.query(models.IPAddrRange)\
            .filter_by(network_group_id=ng_id)\
            .first()
        self.assertIsNone(ip_range)

    def test_delete_network_group_cleanup_ip_addrs(self):
        ng_id = self.env._create_network_group().json["id"]
        node = self.env.create_node(api=False)

        ip_address = []
        for ip_addr in ('10.3.0.2', '10.3.0.3'):
            ip_addr_data = {'network': ng_id,
                            'node': node.id,
                            'ip_addr': ip_addr}
            ip_address.append(ip_addr_data)

        self.db.add_all([models.IPAddr(**ips) for ips in ip_address])
        self.db.flush()

        self.app.delete(
            reverse(
                'NetworkGroupHandler',
                kwargs={'obj_id': ng_id}
            ),
            headers=self.default_headers,
        )
        ips_db = self.db.query(models.IPAddr)\
            .filter_by(network=ng_id)\
            .all()
        self.assertFalse(ips_db)

    def test_cannot_delete_admin_network_group(self):
        admin = objects.NetworkGroup.get_admin_network_group()
        resp = self.app.delete(
            reverse(
                'NetworkGroupHandler',
                kwargs={'obj_id': admin.id}
            ),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(400, resp.status_code)
        self.assertEqual(resp.json_body['message'],
                         'Default Admin-pxe network cannot be deleted')

    def test_cannot_delete_locked_cluster_network_group(self):
        resp = self.env._create_network_group(name='test')
        self.assertEqual(201, resp.status_code)

        net_group = resp.json_body

        with mock.patch('nailgun.db.sqlalchemy.models.Cluster.is_locked',
                        return_value=True):
            resp = self.app.delete(
                reverse(
                    'NetworkGroupHandler',
                    kwargs={'obj_id': net_group['id']}
                ),
                headers=self.default_headers,
                expect_errors=True
            )
            self.assertEqual(400, resp.status_code)
            self.assertEqual(resp.json_body['message'],
                             'Networks cannot be deleted after deployment')

    def test_create_network_group_non_default_name(self):
        resp = self.env._create_network_group(name='test')
        new_ng = resp.json_body
        self.assertEqual(201, resp.status_code)
        self.assertEqual('test', new_ng['name'])

    def test_modify_network_group(self):
        resp = self.env._create_network_group(name='test')

        new_ng = resp.json_body
        new_ng['name'] = 'test2'

        resp = self.env._update_network_group(new_ng)
        updated_ng = resp.json_body

        self.assertEquals('test2', updated_ng['name'])

    def test_update_network_group_ipranges_regenerated(self):
        resp = self.env._create_network_group(
            meta={
                "notation": "ip_ranges",
                "ip_range": ["10.3.0.33", "10.3.0.158"],
            }
        )
        new_ng = resp.json_body
        new_ng["name"] = "test"

        new_ip_ranges = [["172.16.0.1", "172.16.0.10"],
                         ["10.20.0.2", "10.20.0.20"]]
        new_ng["ip_ranges"] = new_ip_ranges

        self.app.put(
            reverse(
                'NetworkGroupHandler',
                kwargs={'obj_id': new_ng['id']}
            ),
            jsonutils.dumps(new_ng),
            headers=self.default_headers
        )

        ip_ranges = self.db.query(models.IPAddrRange)\
            .filter_by(network_group_id=new_ng["id"])\
            .all()
        self.assertItemsEqual(
            new_ip_ranges,
            [[ipr.first, ipr.last] for ipr in ip_ranges]
        )

    def test_update_network_group_ipranges_regenerated_for_cidr(self):
        resp = self.env._create_network_group()
        new_ng = resp.json_body

        new_cidr = "10.3.0.0/20"
        new_ng['cidr'] = new_cidr
        new_ng['name'] = 'test'
        new_ng['meta']['use_gateway'] = True

        generated_range = IPNetwork("10.3.0.0/20")
        new_ip_range = [str(generated_range[2]), str(generated_range[-2])]

        self.app.put(
            reverse(
                'NetworkGroupHandler',
                kwargs={'obj_id': new_ng['id']}
            ),
            jsonutils.dumps(new_ng),
            headers=self.default_headers
        )

        ip_range = self.db.query(models.IPAddrRange)\
            .filter_by(network_group_id=new_ng["id"])\
            .one()
        self.assertEqual(ip_range.first, new_ip_range[0])
        self.assertEqual(ip_range.last, new_ip_range[1])

    def test_duplicate_network_name_on_creation(self):
        resp = self.env._create_network_group()
        self.assertEqual(201, resp.status_code)
        resp = self.env._create_network_group(expect_errors=True)
        self.assertEqual(409, resp.status_code)
        self.assertRegexpMatches(resp.json_body["message"],
                                 'Network with name .* already exists')

    def test_duplicate_network_name_on_change(self):
        resp = self.env._create_network_group(name='test')
        new_ng = resp.json_body

        new_ng['name'] = 'public'

        resp = self.env._update_network_group(new_ng, expect_errors=True)
        self.assertEqual(409, resp.status_code)
        self.assertRegexpMatches(resp.json_body["message"],
                                 'Network with name .* already exists')

    def test_update_same_name(self):
        resp = self.env._create_network_group(name='test')
        new_ng = resp.json_body

        resp = self.env._update_network_group(new_ng, expect_errors=False)
        self.assertEqual(200, resp.status_code)

    def test_update_doesnt_require_group_id(self):
        resp = self.env._create_network_group(name='test')
        new_ng = resp.json_body
        del new_ng['group_id']

        resp = self.env._update_network_group(new_ng, expect_errors=False)
        self.assertEqual(200, resp.status_code)

    def test_update_doesnt_require_id_in_data(self):
        ng_id = self.env._create_network_group(name='test').json_body['id']

        update_data = {'name': 'test2'}

        update_resp = self.app.put(
            reverse(
                'NetworkGroupHandler',
                kwargs={'obj_id': ng_id}
            ),
            jsonutils.dumps(update_data),
            headers=self.default_headers
        )

        self.assertEqual(200, update_resp.status_code)
        self.assertEqual(update_resp.json_body['name'], 'test2')

    def test_invalid_group_id_on_creation(self):
        resp = self.env._create_network_group(expect_errors=True, group_id=-1)
        self.assertEqual(400, resp.status_code)
        self.assertRegexpMatches(resp.json_body["message"],
                                 'Node group with ID -1 does not exist')

    def test_create_network_group_without_vlan(self):
        resp = self.env._create_network_group(vlan=None)
        self.assertEqual(201, resp.status_code)

    def test_modify_network_no_ip_ranges(self):
        resp = self.env._create_network_group(
            name='test',
            meta={"notation": consts.NETWORK_NOTATION.ip_ranges,
                  "ip_range": ["10.3.0.33", "10.3.0.158"]},
            expect_errors=True
        )
        new_ng = resp.json_body

        new_ng.pop('ip_ranges', None)
        new_ng.pop('name', None)

        db_ng = objects.NetworkGroup.get_by_uid(new_ng['id'])
        db_ng.ip_ranges = []
        self.db.flush()

        resp = self.env._update_network_group(new_ng, expect_errors=True)
        self.assertEqual(400, resp.status_code)
        self.assertRegexpMatches(
            resp.json_body['message'],
            'No IP ranges were specified for network {0}'.format(new_ng['id'])
        )

    def test_modify_network_no_cidr(self):
        resp = self.env._create_network_group(name='test', expect_errors=True)
        new_ng = resp.json_body

        new_ng['meta']['notation'] = consts.NETWORK_NOTATION.ip_ranges
        new_ng['ip_ranges'] = ["10.3.0.33", "10.3.0.158"]
        new_ng.pop('cidr', None)
        new_ng.pop('name', None)

        db_ng = objects.NetworkGroup.get_by_uid(new_ng['id'])
        db_ng.cidr = None
        self.db.flush()

        resp = self.env._update_network_group(new_ng, expect_errors=True)
        self.assertEqual(400, resp.status_code)
        self.assertRegexpMatches(
            resp.json_body['message'],
            'No CIDR was specified for network {0}'.format(new_ng['id'])
        )

    def test_modify_network_no_gateway(self):
        resp = self.env._create_network_group(
            meta={"use_gateway": True},
            gateway=None,
            expect_errors=True
        )
        new_ng = resp.json_body

        new_ng['meta']['notation'] = consts.NETWORK_NOTATION.ip_ranges
        new_ng['ip_ranges'] = []
        new_ng.pop('name', None)

        db_ng = objects.NetworkGroup.get_by_uid(new_ng['id'])
        db_ng.gateway = None
        self.db.flush()

        resp = self.env._update_network_group(new_ng, expect_errors=True)
        self.assertEqual(400, resp.status_code)
        self.assertRegexpMatches(
            resp.json_body['message'],
            "'use_gateway' cannot be provided without gateway"
        )

    def test_modify_network_release(self):
        resp = self.env._create_network_group(name='test', expect_errors=True)
        new_ng = resp.json_body

        new_ng['release'] = 100
        new_ng.pop('name', None)

        resp = self.env._update_network_group(new_ng, expect_errors=True)
        self.assertEqual(400, resp.status_code)
        self.assertRegexpMatches(resp.json_body['message'],
                                 'Network release could not be changed.')

    def test_modify_admin_network_group_with_wrong_group_id(self):
        admin = objects.NetworkGroup.get_admin_network_group()
        admin_network_data = {
            'id': admin.id,
            'group_id': objects.Cluster.get_default_group(self.cluster).id,
            'meta': admin.meta
        }
        resp = self.env._update_network_group(admin_network_data,
                                              expect_errors=True)
        self.assertEqual(400, resp.status_code)
        self.assertRegexpMatches(
            resp.json_body['message'],
            'Default Admin-pxe network cannot be changed'
        )
