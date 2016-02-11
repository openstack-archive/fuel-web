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
from nailgun.orchestrator.deployment_graph import AstuteGraph

from nailgun.orchestrator.deployment_serializers import \
    get_serializer_for_cluster

from nailgun.test.integration.test_orchestrator_serializer import \
    BaseDeploymentSerializer

from nailgun.test.integration.test_orchestrator_serializer_80 import \
    TestDeploymentHASerializer80

from nailgun.test.integration.test_orchestrator_serializer_80 import \
    TestDeploymentAttributesSerialization80


class TestSerializer90Mixin(object):
    env_version = "liberty-9.0"


class PrepareDataMixin(object):

    def patch_net_roles_for_release(self):
        rel_id = self.env.create_release(version=self.env_version).id
        rel_db = self.db.query(models.Release).filter_by(id=rel_id).one()

        to_patch = yaml.safe_load("""
      -
        id: "keystone/api"
        default_mapping: "management"
        properties: &default_network_roles_metadata_properties
          subnet: true
          gateway: false
          vip: []
      -
        id: "admin/pxe"
        default_mapping: "fuelweb_admin"
        properties:
          subnet: true
          gateway: true
          vip: []
      -
        id: "swift/api"
        default_mapping: "management"
        properties: *default_network_roles_metadata_properties
      -
        id: "neutron/api"
        default_mapping: "management"
        properties: *default_network_roles_metadata_properties
      -
        id: "sahara/api"
        default_mapping: "management"
        properties: *default_network_roles_metadata_properties
      -
        id: "ceilometer/api"
        default_mapping: "management"
        properties: *default_network_roles_metadata_properties
      -
        id: "aodh/api"
        default_mapping: "management"
        properties: *default_network_roles_metadata_properties
      -
        id: "cinder/api"
        default_mapping: "management"
        properties: *default_network_roles_metadata_properties
      -
        id: "glance/api"
        default_mapping: "management"
        properties: *default_network_roles_metadata_properties
      -
        id: "heat/api"
        default_mapping: "management"
        properties: *default_network_roles_metadata_properties
      -
        id: "nova/api"
        default_mapping: "management"
        properties: *default_network_roles_metadata_properties
      -
        id: "murano/api"
        default_mapping: "management"
        properties: *default_network_roles_metadata_properties
      -
        id: "horizon"
        default_mapping: "management"
        properties: *default_network_roles_metadata_properties
      -
        id: "mgmt/memcache"
        default_mapping: "management"
        properties: *default_network_roles_metadata_properties
      -
        id: "mgmt/database"
        default_mapping: "management"
        properties: *default_network_roles_metadata_properties
      -
        id: "mgmt/messaging"
        default_mapping: "management"
        properties: *default_network_roles_metadata_properties
      -
        id: "mgmt/corosync"
        default_mapping: "management"
        properties: *default_network_roles_metadata_properties
      -
        id: "mgmt/vip"
        default_mapping: "management"
        properties:
          subnet: true
          gateway: false
          vip:
            -
              name: "vrouter"
              namespace: "vrouter"
              alias: "management_vrouter_vip"
            -
              name: "management"
              namespace: "haproxy"
              alias: "management_vip"
      -
        id: "public/vip"
        default_mapping: "public"
        properties:
          subnet: true
          gateway: true
          vip:
            -
              name: "vrouter_pub"
              namespace: "vrouter"
              alias: "public_vrouter_vip"
            -
              name: "public"
              namespace: "haproxy"
              alias: "public_vip"
      -
        id: "neutron/private"
        default_mapping: "private"
        properties:
          subnet: false
          gateway: false
          vip: []
      -
        id: "neutron/mesh"
        default_mapping: "private"
        properties: *default_network_roles_metadata_properties
      -
        id: "neutron/floating"
        default_mapping: "public"
        properties:
          subnet: false
          gateway: false
          vip: []
      -
        id: "swift/replication"
        default_mapping: "storage"
        properties: *default_network_roles_metadata_properties
      -
        id: "ceph/public"
        default_mapping: "management"
        properties: *default_network_roles_metadata_properties
      -
        id: "ceph/radosgw"
        default_mapping: "public"
        properties: *default_network_roles_metadata_properties
      -
        id: "ceph/replication"
        default_mapping: "storage"
        properties: *default_network_roles_metadata_properties
      -
        id: "cinder/iscsi"
        default_mapping: "storage"
        properties: *default_network_roles_metadata_properties
      -
        id: "mongo/db"
        default_mapping: "management"
        properties: *default_network_roles_metadata_properties
      -
        id: "fw-admin"
        default_mapping: "fuelweb_admin"
        properties:
          subnet: true
          gateway: true
          vip: []
      -
        id: "management"
        default_mapping: "management"
        properties: *default_network_roles_metadata_properties
      -
        id: "ex"
        default_mapping: "public"
        properties:
          subnet: true
          gateway: true
          vip: []
      -
        id: "storage"
        default_mapping: "storage"
        properties: *default_network_roles_metadata_properties
      -
        id: "nova/migration"
        default_mapping: "management"
        properties: *default_network_roles_metadata_properties
        """)
        rel_db.network_roles_metadata = to_patch
        self.db.flush()
        return rel_db


class BaseTestDeploymentAttributesSerialization90(BaseDeploymentSerializer,
                                                  PrepareDataMixin):
    management = ['keystone/api', 'neutron/api', 'swift/api', 'sahara/api',
                  'ceilometer/api', 'aodh/api', 'cinder/api', 'glance/api',
                  'heat/api', 'nova/api', 'murano/api', 'horizon',
                  'management', 'mgmt/database', 'mgmt/messaging',
                  'mgmt/corosync', 'mgmt/memcache', 'mgmt/vip', 'mongo/db',
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
    env_version = 'liberty-9.0'

    def setUp(self):
        super(BaseTestDeploymentAttributesSerialization90, self).setUp()
        self.cluster = self.create_env(consts.CLUSTER_MODES.ha_compact)

        objects.Cluster.prepare_for_deployment(self.env.clusters[-1])
        self.cluster_db = self.db.query(models.Cluster).get(self.cluster['id'])
        serializer_type = get_serializer_for_cluster(self.cluster_db)
        self.serializer = serializer_type(AstuteGraph(self.cluster_db))
        self.serialized_for_astute = self.serializer.serialize(
            self.cluster_db, self.cluster_db.nodes)
        self.vm_data = self.env.read_fixtures(['vmware_attributes'])

    def create_env(self, mode):
        release = self.patch_net_roles_for_release()

        return self.env.create(
            cluster_kwargs={
                'release_id': release.id,
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


class TestDeploymentAttributesSerialization90(
    TestSerializer90Mixin,
    TestDeploymentAttributesSerialization80
):
    pass


class TestDeploymentHASerializer90(
    TestSerializer90Mixin,
    TestDeploymentHASerializer80
):
    def test_glance_properties(self):
        self.check_no_murano_data()
