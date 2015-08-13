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

from netaddr import IPNetwork

from oslo_serialization import jsonutils

from nailgun.db.sqlalchemy import models
from nailgun import objects
from nailgun.test.base import BaseIntegrationTest
from nailgun.utils import reverse


class TestHandlers(BaseIntegrationTest):

    def setUp(self):
        super(TestHandlers, self).setUp()
        self.cluster = self.env.create_cluster(api=False)

    def _create_network_group(self, expect_errors=False, **kwargs):
        ng = {
            "release": self.cluster.release.id,
            "name": "external",
            "vlan_start": 50,
            "cidr": "10.3.0.0/24",
            "gateway": "10.3.0.1",
            "group_id": objects.Cluster.get_default_group(self.cluster).id,
            "meta": {"notation": "cidr"}
        }

        ng.update(kwargs)

        resp = self.app.post(
            reverse('NetworkGroupCollectionHandler'),
            jsonutils.dumps(ng),
            headers=self.default_headers,
            expect_errors=expect_errors,
        )

        return resp

    def test_create_network_group_w_cidr(self):
        resp = self._create_network_group()
        self.assertEqual(201, resp.status_code)
        ng_data = jsonutils.loads(resp.body)
        ng = objects.NetworkGroup.get_by_uid(ng_data['id'])
        self.assertEqual(len(ng.ip_ranges), 1)
        self.assertEqual(ng.ip_ranges[0].first, "10.3.0.2")
        self.assertEqual(ng.ip_ranges[0].last, "10.3.0.254")

    def test_create_network_group_w_ip_range(self):
        resp = self._create_network_group(
            meta={
                "notation": "ip_ranges",
                "ip_range": ["10.3.0.33", "10.3.0.158"]
            }
        )
        self.assertEqual(201, resp.status_code)
        ng_data = jsonutils.loads(resp.body)
        ng = objects.NetworkGroup.get_by_uid(ng_data['id'])
        self.assertEqual(len(ng.ip_ranges), 1)
        self.assertEqual(ng.ip_ranges[0].first, "10.3.0.33")
        self.assertEqual(ng.ip_ranges[0].last, "10.3.0.158")

    def test_create_network_group_wo_notation(self):
        resp = self._create_network_group(meta={"notation": None})
        self.assertEqual(201, resp.status_code)
        ng_data = jsonutils.loads(resp.body)
        ng = objects.NetworkGroup.get_by_uid(ng_data['id'])
        self.assertEqual(len(ng.ip_ranges), 0)

    def test_create_network_group_error(self):
        resp = self._create_network_group(
            meta={"notation": "new"},
            expect_errors=True
        )
        self.assertEqual(400, resp.status_code)
        self.assertEqual(resp.json_body["message"],
                         "IPAddrRange object cannot be created for network "
                         "'external' with notation='new', ip_range='None'")

        resp = self._create_network_group(
            meta={"notation": "ip_ranges"},
            expect_errors=True
        )
        self.assertEqual(400, resp.status_code)
        self.assertEqual(resp.json_body["message"],
                         "IPAddrRange object cannot be created for network "
                         "'external' with notation='ip_ranges', "
                         "ip_range='None'")

        resp = self._create_network_group(
            meta={"notation": "ip_ranges",
                  "ip_range": ["10.3.0.33"]},
            expect_errors=True
        )
        self.assertEqual(400, resp.status_code)
        self.assertEqual(resp.json_body["message"],
                         "IPAddrRange object cannot be created for network "
                         "'external' with notation='ip_ranges', "
                         "ip_range='[u'10.3.0.33']'")

    def test_get_network_group(self):
        resp = self._create_network_group(name='test')
        self.assertEqual(201, resp.status_code)
        new_ng = jsonutils.loads(resp.body)

        net_group = jsonutils.loads(resp.body)

        resp = self.app.get(
            reverse(
                'NetworkGroupHandler',
                kwargs={'obj_id': net_group['id']}
            ),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        self.assertEqual(jsonutils.loads(resp.body), new_ng)

    def test_delete_network_group(self):
        resp = self._create_network_group(name='test')
        self.assertEqual(201, resp.status_code)

        net_group = jsonutils.loads(resp.body)

        resp = self.app.delete(
            reverse(
                'NetworkGroupHandler',
                kwargs={'obj_id': net_group['id']}
            ),
            headers=self.default_headers
        )
        self.assertEqual(204, resp.status_code)

    def test_delete_network_group_cleanup_ip_range(self):
        ng_id = self._create_network_group(
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
        ng_id = self._create_network_group().json["id"]
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
        admin = objects.Cluster.get_network_manager().get_admin_network_group()
        resp = self.app.delete(
            reverse(
                'NetworkGroupHandler',
                kwargs={'obj_id': admin.id}
            ),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(400, resp.status_code)
        self.assertEqual(resp.json_body["message"],
                         'Default Admin-pxe network cannot be deleted')

    def test_create_network_group_non_default_name(self):
        resp = self._create_network_group(name='test')
        new_ng = jsonutils.loads(resp.body)
        self.assertEqual(201, resp.status_code)
        self.assertEqual('test', new_ng['name'])

    def test_modify_network_group(self):
        resp = self._create_network_group(name='test')
        new_ng = jsonutils.loads(resp.body)

        new_ng['name'] = 'test2'

        resp = self.app.put(
            reverse(
                'NetworkGroupHandler',
                kwargs={'obj_id': new_ng['id']}
            ),
            jsonutils.dumps(new_ng),
            headers=self.default_headers
        )
        updated_ng = jsonutils.loads(resp.body)

        self.assertEquals('test2', updated_ng['name'])

    def test_update_network_group_ipranges_regenerated(self):
        resp = self._create_network_group(
            meta={
                "notation": "ip_ranges",
                "ip_range": ["10.3.0.33", "10.3.0.158"]
            }
        )
        new_ng = jsonutils.loads(resp.body)
        new_ng["name"] = "test"

        new_ip_range = ["172.16.0.1", "172.16.0.10"]
        new_ng["meta"]["ip_range"] = new_ip_range

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

    def test_update_network_group_ipranges_regenerated_for_cidr(self):
        resp = self._create_network_group()
        new_ng = jsonutils.loads(resp.body)

        new_cidr = "10.3.0.1/20"
        new_ng['cidr'] = new_cidr
        new_ng['name'] = 'test'

        generated_range = IPNetwork("10.3.0.1/20")
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
        resp = self._create_network_group()
        self.assertEqual(201, resp.status_code)
        resp = self._create_network_group(expect_errors=True)
        self.assertEqual(409, resp.status_code)
        self.assertRegexpMatches(resp.json_body["message"],
                                 'Network with name .* already exists')

    def test_duplicate_network_name_on_change(self):
        resp = self._create_network_group(name='test')
        new_ng = jsonutils.loads(resp.body)

        new_ng['name'] = 'public'

        resp = self.app.put(
            reverse(
                'NetworkGroupHandler',
                kwargs={'obj_id': new_ng['id']}
            ),
            jsonutils.dumps(new_ng),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(409, resp.status_code)
        self.assertRegexpMatches(resp.json_body["message"],
                                 'Network with name .* already exists')

    def test_invalid_group_id_on_creation(self):
        resp = self._create_network_group(expect_errors=True, group_id=-1)
        self.assertEqual(400, resp.status_code)
        self.assertRegexpMatches(resp.json_body["message"],
                                 'Node group with ID -1 does not exist')

    def test_invalid_group_id_on_change(self):
        resp = self._create_network_group(name='test')
        new_ng = jsonutils.loads(resp.body)

        new_ng['group_id'] = -1

        resp = self.app.put(
            reverse(
                'NetworkGroupHandler',
                kwargs={'obj_id': new_ng['id']}
            ),
            jsonutils.dumps(new_ng),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(400, resp.status_code)
        self.assertRegexpMatches(resp.json_body["message"],
                                 'Node group with ID -1 does not exist')

    def test_create_network_group_without_vlan(self):
        resp = self._create_network_group(vlan=None)
        self.assertEqual(201, resp.status_code)
