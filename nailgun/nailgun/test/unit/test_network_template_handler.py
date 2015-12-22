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

from nailgun.db import db

from nailgun import consts
from nailgun.test import base
from nailgun.test.base import BaseIntegrationTest
from nailgun.utils import reverse


class TestHandlers(BaseIntegrationTest):

    def get_template(self, cluster_id, expect_errors=False):
        resp = self.app.get(
            reverse(
                'TemplateNetworkConfigurationHandler',
                kwargs={'cluster_id': cluster_id}
            ),
            headers=self.default_headers,
            expect_errors=expect_errors
        )

        return resp

    def test_network_template_upload(self):
        cluster = self.env.create_cluster(api=False)
        template = self.env.read_fixtures(['network_template_80'])[0]

        resp = self.app.put(
            reverse(
                'TemplateNetworkConfigurationHandler',
                kwargs={'cluster_id': cluster.id},
            ),
            jsonutils.dumps(template),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        self.assertEquals(template, resp.json_body)

        resp = self.get_template(cluster.id)
        self.assertEqual(200, resp.status_code)
        self.assertEqual(template, resp.json_body)

    def test_network_template_upload_on_multi_group_cluster(self):
        cluster = self.env.create_cluster(
            api=False,
            net_provider=consts.CLUSTER_NET_PROVIDERS.neutron
        )
        cluster.release.version = '1111-7.0'

        custom_group_name = 'group-custom-1'
        resp = self.env.create_node_group(
            name=custom_group_name, cluster_id=cluster.id
        )
        custom_group = resp.json_body

        node1 = self.env.create_nodes_w_interfaces_count(
            1, 5,
            cluster_id=cluster.id,
            roles=["controller"],
        )[0]
        node2 = self.env.create_nodes_w_interfaces_count(
            1, 5,
            cluster_id=cluster.id,
            roles=["compute"],
            group_id=custom_group['id'],
        )[0]

        template = self.env.read_fixtures(['network_template_70'])[0]

        resp = self.app.put(
            reverse(
                'TemplateNetworkConfigurationHandler',
                kwargs={'cluster_id': cluster.id},
            ),
            jsonutils.dumps(template),
            headers=self.default_headers
        )
        self.assertEqual(200, resp.status_code)
        self.assertDictEqual(
            node1.network_template['templates'],
            base.get_nodegroup_network_schema_template(template, 'default')
        )
        self.assertDictEqual(
            node2.network_template['templates'],
            base.get_nodegroup_network_schema_template(
                template, custom_group_name)
        )

    def test_wrong_network_template_upload_failed(self):
        cluster = self.env.create_cluster(api=False)
        template = self.env.read_fixtures(['network_template_80'])[0]
        template['adv_net_template']['default'] = {}

        resp = self.app.put(
            reverse(
                'TemplateNetworkConfigurationHandler',
                kwargs={'cluster_id': cluster.id},
            ),
            jsonutils.dumps(template),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(400, resp.status_code)

    def test_template_not_set(self):
        resp = self.get_template(1, expect_errors=True)
        self.assertEqual(404, resp.status_code)

    def check_put_delete_template(self, cluster, forbidden=False):
        template = self.env.read_fixtures(['network_template_80'])[0]
        resp = self.app.put(
            reverse(
                'TemplateNetworkConfigurationHandler',
                kwargs={'cluster_id': cluster.id},
            ),
            jsonutils.dumps(template),
            headers=self.default_headers,
            expect_errors=forbidden
        )
        if not forbidden:
            self.assertEqual(resp.status_code, 200)
        else:
            self.assertEqual(resp.status_code, 403)

        resp = self.app.delete(
            reverse(
                'TemplateNetworkConfigurationHandler',
                kwargs={'cluster_id': cluster.id},
            ),
            headers=self.default_headers,
            expect_errors=forbidden
        )
        if not forbidden:
            self.assertEqual(resp.status_code, 204)
            resp = self.get_template(cluster.id)
            self.assertEquals(None, resp.json_body)
        else:
            self.assertEqual(resp.status_code, 403)

    def test_put_delete_template(self):
        cluster = self.env.create_cluster(api=False)
        self.check_put_delete_template(cluster)

    def test_put_delete_template_after_deployment(self):
        cluster = self.env.create_cluster(api=False)
        allowed = [consts.CLUSTER_STATUSES.new,
                   consts.CLUSTER_STATUSES.stopped,
                   consts.CLUSTER_STATUSES.operational,
                   consts.CLUSTER_STATUSES.error]
        for status in consts.CLUSTER_STATUSES:
            cluster.status = status
            # need commit because rollback is called when handler exits with
            # error (403 in this case)
            db().commit()
            self.check_put_delete_template(cluster, status not in allowed)
