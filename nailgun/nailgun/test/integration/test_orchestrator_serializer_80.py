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

import yaml

from nailgun import consts
from nailgun.db.sqlalchemy import models
from nailgun import objects

from nailgun.orchestrator.deployment_serializers import \
    get_serializer_for_cluster
from nailgun.orchestrator.neutron_serializers import \
    NeutronNetworkDeploymentSerializer80
from nailgun.orchestrator.neutron_serializers import \
    NeutronNetworkTemplateSerializer80
from nailgun.test.integration.test_orchestrator_serializer import \
    BaseDeploymentSerializer
from nailgun.test.integration.test_orchestrator_serializer import \
    TestSerializeInterfaceDriversData
from nailgun.test.integration.test_orchestrator_serializer_70 import \
    BaseTestDeploymentAttributesSerialization70
from nailgun.test.integration.test_orchestrator_serializer_70 import \
    TestDeploymentHASerializer70


class TestNetworkTemplateSerializer80(BaseDeploymentSerializer):
    env_version = '2015.1.0-8.0'
    prepare_for_deployment = objects.NodeCollection.prepare_for_deployment

    def setUp(self, *args):
        super(TestNetworkTemplateSerializer80, self).setUp()
        cluster = self.create_env(consts.CLUSTER_MODES.ha_compact)
        self.net_template = self.env.read_fixtures(['network_template'])[0]
        self.cluster = self.db.query(models.Cluster).get(cluster['id'])

    def test_get_net_provider_serializer(self):
        serializer = get_serializer_for_cluster(self.cluster)
        self.cluster.network_config.configuration_template = None

        net_serializer = serializer.get_net_provider_serializer(self.cluster)
        self.assertIs(net_serializer, NeutronNetworkDeploymentSerializer80)

        self.cluster.network_config.configuration_template = \
            self.net_template
        net_serializer = serializer.get_net_provider_serializer(self.cluster)
        self.assertIs(net_serializer, NeutronNetworkTemplateSerializer80)


class TestSerializer80Mixin(object):
    env_version = "2015.1.0-8.0"

    def prepare_for_deployment(self, nodes, *_):
        objects.NodeCollection.prepare_for_deployment(nodes)


class TestSerializeInterfaceDriversData80(
    TestSerializer80Mixin,
    TestSerializeInterfaceDriversData
):
    pass


class TestDeploymentHASerializer80(
    TestSerializer80Mixin,
    TestDeploymentHASerializer70
):
    pass


class TestDeploymentAttributesSerialization80(
    BaseTestDeploymentAttributesSerialization70
):
    env_version = '2015.1.0-8.0'
    plugin_network_roles = yaml.safe_load("""
- id: "unmapped_role"
  default_mapping: "non_existing_net"
  properties:
    subnet: true
    gateway: false
    vip:
       - name: "unmapped_vip"
         namespace: "haproxy"
        """)

    def test_network_scheme(self):
        self._add_plugin_network_roles()
        self.serialized_for_astute = self.serializer.serialize(
            self.cluster_db, self.cluster_db.nodes)
        for node in self.serialized_for_astute:
            roles = node['network_scheme']['roles']
            node = objects.Node.get_by_uid(node['uid'])

            expected_roles = zip(
                self.management, ['br-mgmt'] * len(self.management))
            expected_roles += zip(
                self.fuelweb_admin, ['br-fw-admin'] * len(self.fuelweb_admin))
            expected_roles += zip(
                self.storage, ['br-storage'] * len(self.storage))

            if objects.Node.should_have_public(node):
                expected_roles += zip(
                    self.public, ['br-ex'] * len(self.public))
                expected_roles += [('neutron/floating', 'br-floating')]

            if node.cluster.network_config.segmentation_type == \
                    consts.NEUTRON_SEGMENT_TYPES.vlan:
                expected_roles += [('neutron/private', 'br-prv')]

            if node.cluster.network_config.segmentation_type in \
                    (consts.NEUTRON_SEGMENT_TYPES.gre,
                     consts.NEUTRON_SEGMENT_TYPES.tun):
                expected_roles += [('neutron/mesh', 'br-mesh')]

            self.assertEqual(roles, dict(expected_roles))
