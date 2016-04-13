# -*- coding: utf-8 -*-

#    Copyright 2016 Mirantis, Inc.
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

import uuid

from oslo_serialization import jsonutils
import six

from nailgun import objects
from nailgun.test import base


class TestNetTemplateMalformedNICMappingApply(base.BaseIntegrationTest):

    def setUp(self):
        super(TestNetTemplateMalformedNICMappingApply, self).setUp()

        self.cluster = self.env.create(
            release_kwargs={'api': False, 'version': 'mitaka-9.0'},
            cluster_kwargs={'api': False}
        )

        self.node = self.create_controller()

        self.modified_template = self.mutilate_nic_mapping(
            self._prepare_template(), self.node)

    def create_controller(self):
        node = self.env.create_node(roles=['controller'])
        node.roles = ['controller']
        self.db.flush()

        return node

    def _prepare_template(self):
        template = self.env.read_fixtures(['network_template_90'])[0]
        template.pop('pk')  # PK is not needed
        return template

    def add_node_to_cluster(self, cluster, node, expect_errors=False):
        return self.app.put(
            base.reverse(
                'NodeHandler',
                kwargs={'obj_id': node.id}
            ),
            params=jsonutils.dumps({'cluster_id': cluster.id}),
            headers=self.default_headers,
            expect_errors=expect_errors
        )

    def upload_template(self, cluster, template, expect_errors=False):
        return self.app.put(
            base.reverse(
                'TemplateNetworkConfigurationHandler',
                kwargs={'cluster_id': cluster.id},
            ),
            jsonutils.dumps(template),
            headers=self.default_headers,
            expect_errors=expect_errors
        )

    def mutilate_nic_mapping(self, template, node):
        # change names of those interfaces in NIC mapping for which networks
        # must be assigned after building of networks to nodes mapping; this
        # must result in error as look up by NIC name is performed for node
        # in such case, and network controllers of that node will have
        # different names, thus will not be returned by query

        node_nic_names = [nic.name for nic in node.nic_interfaces]
        # NOTE(aroma): in order to make this method more general let's use only
        # 'default' node group, as in some test cases modified template
        # is assigned for cluster before nodes, and consequently their node
        # groups are not yet known by the moment
        nic_mapping = \
            template['adv_net_template']['default']['nic_mapping']

        new_mapping = {}
        for substitute, iface_name in six.iteritems(nic_mapping['default']):
            if iface_name in node_nic_names:
                new_mapping[substitute] = uuid.uuid4().hex
            else:
                new_mapping[substitute] = iface_name

        nic_mapping['default'] = new_mapping

        return template

    def check_err_resp(self, resp):
        self.assertEqual(resp.status_code, 400)
        self.assertIn('does not exist for node', resp.json_body['message'])

    def test_fail_for_cluster_w_nodes(self):
        self.add_node_to_cluster(self.cluster, self.node)

        # network template is applied for nodes (if any) when it is uploaded
        resp = self.upload_template(self.cluster, self.modified_template,
                                    expect_errors=True)
        self.check_err_resp(resp)

    def test_fail_if_set_node_via_single_handler(self):
        # NOTE(aroma): the template contains data pertaining to node groups;
        # so if 'nic_mapping' subsection is malformed the template can
        # still be uploaded successfully, but only in case cluster does not
        # have assigned nodes bound to that particular node group
        self.upload_template(self.cluster, self.modified_template)

        # network template is applied for node if it is being added to
        # cluster (via handler for single objects)
        resp = self.add_node_to_cluster(self.cluster, self.node,
                                        expect_errors=True)
        self.check_err_resp(resp)

    def test_fail_if_set_node_via_collect_handler(self):
        # node could be assigned to cluster via NodeCollectionHandler
        # too; please, see comments for previous test case as the main idea
        # here is the same except different handler must be checked
        self.upload_template(self.cluster, self.modified_template)

        resp = self.app.put(
            base.reverse("NodeCollectionHandler"),
            params=jsonutils.dumps(
                [{'id': self.node.id, 'cluster_id': self.cluster.id}]
            ),
            headers=self.default_headers,
            expect_errors=True
        )

        self.check_err_resp(resp)

    def test_fail_if_set_node_via_cluster_handler(self):
        # node could be set via PUT to ClusterHandler; network template is
        # applied to the node in such case; ditto as in comments for
        # previous test cases
        self.upload_template(self.cluster, self.modified_template)

        self.node.nodegroup = objects.Cluster.get_default_group(self.cluster)

        resp = self.app.put(
            base.reverse(
                "ClusterHandler",
                kwargs={'obj_id': self.cluster.id}
            ),
            params=jsonutils.dumps({'nodes': [self.node.id]}),
            headers=self.default_headers,
            expect_errors=True
        )

        self.check_err_resp(resp)
