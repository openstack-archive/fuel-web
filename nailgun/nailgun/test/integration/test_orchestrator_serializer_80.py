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
from nailgun.db.sqlalchemy import models
from nailgun import objects

from nailgun.orchestrator.deployment_graph import AstuteGraph
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
    TestDeploymentHASerializer70
from nailgun.utils import reverse


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


class TestDeploymentAttributesSerialization80(BaseDeploymentSerializer):
    env_version = '2015.1.0-8.0'

    def setUp(self):
        super(TestDeploymentAttributesSerialization80, self).setUp()
        self.cluster = self.env.create(
            release_kwargs={'version': self.env_version},
            cluster_kwargs={
                'mode': consts.CLUSTER_MODES.ha_compact,
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': consts.NEUTRON_SEGMENT_TYPES.vlan})
        self.cluster_db = self.db.query(models.Cluster).get(self.cluster['id'])
        serializer_type = get_serializer_for_cluster(self.cluster_db)
        self.serializer = serializer_type(AstuteGraph(self.cluster_db))

    def test_baremetal_transformations(self):
        attrs = self.cluster_db.attributes.editable
        attrs['additional_components']['ironic']['value'] = True
        self.app.patch(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': self.cluster['id']}),
            params=jsonutils.dumps({'editable': attrs}),
            headers=self.default_headers
        )
        node_kwargs = {
            'cluster_id': self.cluster['id'],
            'roles': ['primary-controller'],
            'pending_addition': True}
        self.env.create_node(**node_kwargs)
        self.db.refresh(self.cluster_db)
        self.prepare_for_deployment(self.env.nodes)
        serialized_for_astute = self.serializer.serialize(
            self.cluster_db, self.cluster_db.nodes)
        for node in serialized_for_astute:
            transformations = node['network_scheme']['transformations']
            baremetal_brs = filter(lambda t: t.get('name') ==
                                   consts.DEFAULT_BRIDGES_NAMES.br_baremetal,
                                   transformations)
            baremetal_ports = filter(lambda t: t.get('name') == "eth0.104",
                                     transformations)
            expected_patch = {
                'action': 'add-patch',
                'bridges': [consts.DEFAULT_BRIDGES_NAMES.br_ironic,
                            consts.DEFAULT_BRIDGES_NAMES.br_baremetal],
                'provider': 'ovs'}
            self.assertEqual(len(baremetal_brs), 1)
            self.assertEqual(len(baremetal_ports), 1)
            self.assertEqual(baremetal_ports[0]['bridge'],
                             consts.DEFAULT_BRIDGES_NAMES.br_baremetal)
            self.assertIn(expected_patch, transformations)


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
