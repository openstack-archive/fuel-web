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

import six
import yaml

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


class BaseTestDeploymentAttributesSerialization80(BaseDeploymentSerializer):
    management = ['keystone/api', 'neutron/api', 'swift/api', 'sahara/api',
                  'ceilometer/api', 'cinder/api', 'glance/api', 'heat/api',
                  'nova/api', 'murano/api', 'horizon', 'management',
                  'mgmt/database', 'mgmt/messaging', 'mgmt/corosync',
                  'mgmt/memcache', 'mgmt/vip', 'mongo/db',
                  'ceph/public', 'nova/migration']
    fuelweb_admin = ['admin/pxe', 'fw-admin']
    neutron = ['neutron/private', 'neutron/floating']
    storage = ['storage', 'ceph/replication', 'swift/replication',
               'cinder/iscsi']
    public = ['ex', 'public/vip', 'ceph/radosgw']
    private = ['neutron/mesh']

    networks = ['fuelweb_admin', 'storage', 'management', 'public', 'private']

    # Must be set in subclasses
    segmentation_type = None
    env_version = '2015.1.0-8.0'
    prepare_for_deployment = objects.NodeCollection.prepare_for_deployment

    TASKS = """
- id: test_network_roles
  type: puppet
  groups: [controller, primary-controller, compute]
  network_roles: [%s]
  parameters:
    puppet_manifest: /etc/puppet/manifests/controller.pp
    puppet_modules: /etc/puppet/modules
    timeout: 360
- id: primary-controller
  type: group
  role: [primary-controller]
  parameters:
  parameters:
    strategy:
      type: one_by_one
- id: controller
  type: group
  role: [controller]
  requires: [primary-controller]
  parameters:
   strategy:
     type: parallel
     amount: 2
- id: compute
  type: group
  role: [compute]
  requires: [controller]
  parameters:
   strategy:
     type: parallel
"""

    def setUp(self):
        super(BaseTestDeploymentAttributesSerialization80, self).setUp()
        self.cluster = self.create_env(consts.CLUSTER_MODES.ha_compact)

        self.prepare_for_deployment(self.env.nodes)
        self.cluster_db = self.db.query(models.Cluster).get(self.cluster['id'])
        serializer_type = get_serializer_for_cluster(self.cluster_db)
        self.serializer = serializer_type(AstuteGraph(self.cluster_db))
        self.serialized_for_astute = self.serializer.serialize(
            self.cluster_db, self.cluster_db.nodes)
        self.vm_data = self.env.read_fixtures(['vmware_attributes'])

    def create_env(self, mode):
        deployment_tasks = yaml.load(self.TASKS % ', '.join(
            self.management + self.fuelweb_admin + self.storage +
            self.public + self.private))
        return self.env.create(
            release_kwargs={
                'version': self.env_version,
                'deployment_tasks': deployment_tasks},
            cluster_kwargs={
                'mode': mode,
                'net_provider': consts.CLUSTER_NET_PROVIDERS.neutron,
                'net_segment_type': self.segmentation_type},
            nodes_kwargs=[
                {'roles': ['controller'],
                 'pending_addition': True},
                {'roles': ['compute'],
                 'pending_addition': True}])

    def check_vips_serialized(self, node_data):
        vips_names = ['vrouter', 'management', 'vrouter_pub', 'public']
        # check that vip-related info is not in root
        self.assertTrue(all(vip_name not in node_data
                            for vip_name in vips_names))
        vips_data = node_data['network_metadata']['vips']
        self.assertItemsEqual(vips_data,
                              vips_names)
        for vip in vips_names:
            self.assertItemsEqual(
                vips_data[vip],
                ['network_role', 'namespace', 'ipaddr', 'node_roles']
            )


class TestDeploymentAttributesSerialization80(
    BaseTestDeploymentAttributesSerialization80
):
    segmentation_type = consts.NEUTRON_SEGMENT_TYPES.vlan

    def test_network_scheme(self):
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

    def test_network_metadata(self):
        neutron_serializer = self.serializer.get_net_provider_serializer(
            self.cluster_db)
        for node_data in self.serialized_for_astute:
            self.assertItemsEqual(
                node_data['network_metadata'], ['nodes', 'vips'])
            for k, v in six.iteritems(node_data['network_metadata']['nodes']):
                self.assertItemsEqual(
                    v,
                    ['uid', 'fqdn', 'name', 'user_node_name',
                     'swift_zone', 'node_roles', 'network_roles']
                )
                node = objects.Node.get_by_uid(v['uid'])
                ip_by_net = neutron_serializer.get_network_to_ip_mapping(node)

                self.assertEqual(objects.Node.get_slave_name(node), k)
                self.assertEqual(v['uid'], node.uid)
                self.assertEqual(v['fqdn'], objects.Node.get_node_fqdn(node))
                self.assertEqual(v['name'], k)
                self.assertEqual(v['user_node_name'], node.name)
                self.assertEqual(v['swift_zone'], node.uid)

                network_roles = zip(self.management,
                                    [ip_by_net['management']] * len(
                                        self.management))
                network_roles += zip(self.fuelweb_admin,
                                     [ip_by_net['fuelweb_admin']] * len(
                                         self.fuelweb_admin))
                network_roles += zip(
                    self.storage, [ip_by_net['storage']] * len(self.storage))
                network_roles += zip(self.neutron, [None] * len(self.neutron))

                if objects.Node.should_have_public(node):
                    network_roles += zip(
                        self.public, [ip_by_net['public']] * len(self.public))

                if node.cluster.network_config.segmentation_type in \
                        (consts.NEUTRON_SEGMENT_TYPES.gre,
                         consts.NEUTRON_SEGMENT_TYPES.tun):
                    network_roles += zip(
                        self.private,
                        [ip_by_net['private']] * len(self.private))

                self.assertEqual(v['network_roles'], dict(network_roles))
            self.check_vips_serialized(node_data)
