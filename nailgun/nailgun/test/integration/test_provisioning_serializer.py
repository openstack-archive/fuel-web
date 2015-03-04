# -*- coding: utf-8 -*-

#    Copyright 2013 Mirantis, Inc.
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


from nailgun import consts
from nailgun.db.sqlalchemy.models import Node
from nailgun.orchestrator import provisioning_serializers as ps
from nailgun.test.base import BaseIntegrationTest


class TestGetSerializerForCluster(BaseIntegrationTest):

    def _get_cluster(self, version):
        """Returns cluster object of a given version."""
        release = self.env.create_release(api=False, version=version)
        cluster = self.env.create_cluster(api=False, release_id=release.id)
        return cluster

    def test_env_5_0(self):
        cluster = self._get_cluster('2014.1')
        serializer = ps.get_serializer_for_cluster(cluster)

        self.assertIs(serializer, ps.ProvisioningSerializer)

    def test_env_5_0_1(self):
        cluster = self._get_cluster('2014.1.1-5.0.1')
        serializer = ps.get_serializer_for_cluster(cluster)

        self.assertIs(serializer, ps.ProvisioningSerializer)

    def test_env_5_1(self):
        cluster = self._get_cluster('2014.1.1-5.1')
        serializer = ps.get_serializer_for_cluster(cluster)

        self.assertIs(serializer, ps.ProvisioningSerializer)

    def test_env_5_1_1(self):
        cluster = self._get_cluster('2014.1.1-5.1.1')
        serializer = ps.get_serializer_for_cluster(cluster)

        self.assertIs(serializer, ps.ProvisioningSerializer)

    def test_env_6_0(self):
        cluster = self._get_cluster('2014.2-6.0')
        serializer = ps.get_serializer_for_cluster(cluster)

        self.assertIs(serializer, ps.ProvisioningSerializer)

    def test_env_6_0_1(self):
        cluster = self._get_cluster('2014.2-6.0.1')
        serializer = ps.get_serializer_for_cluster(cluster)

        self.assertIs(serializer, ps.ProvisioningSerializer)

    def test_env_6_1(self):
        cluster = self._get_cluster('2014.2-6.1')
        serializer = ps.get_serializer_for_cluster(cluster)

        self.assertIs(serializer, ps.ProvisioningSerializer61)


class TestProvisioningSerializer(BaseIntegrationTest):

    def test_ubuntu_serializer(self):
        release = self.env.create_release(
            api=False,
            operating_system='Ubuntu')

        self.env.create(
            cluster_kwargs={
                'release_id': release.id},
            nodes_kwargs=[
                {'roles': ['controller'], 'pending_addition': True},
                {'roles': ['compute'], 'pending_addition': True}])

        cluster_db = self.env.clusters[0]
        serialized_cluster = ps.serialize(cluster_db, cluster_db.nodes)

        for node in serialized_cluster['nodes']:
            node_db = self.db.query(Node).filter_by(
                fqdn=node['hostname']
            ).first()
            self.assertEqual(
                node['kernel_options']['netcfg/choose_interface'],
                node_db.admin_interface.mac)


class TestProvisioningSerializer61(BaseIntegrationTest):

    serializer = ps.ProvisioningSerializer61

    def test_ubuntu_prov_task_for_images(self):
        release = self.env.create_release(
            api=False, operating_system=consts.RELEASE_OS.ubuntu)
        self.cluster = self.env.create_cluster(
            api=False, release_id=release.id)
        self.cluster.attributes.editable['provision']['method'] = \
            consts.PROVISION_METHODS.image

        serialized_info = self.serializer.serialize(self.cluster, [])

        self.assertIn('pre_provision', serialized_info)
        self.assertTrue(filter(
            lambda task: all([
                task['uids'] == ['master'],
                task['type'] == 'shell',
                task['parameters']['cmd'].startswith('fuel-image')
            ]),
            serialized_info['pre_provision']))
        self.assertFalse(filter(
            lambda task: all([
                task['uids'] == ['master'],
                task['type'] == 'shell',
                task['parameters']['cmd'].startswith(
                    'download-debian-installer')
            ]),
            serialized_info['pre_provision']))

    def test_ubuntu_prov_task_for_cobbler(self):
        release = self.env.create_release(
            api=False, operating_system=consts.RELEASE_OS.ubuntu)
        self.cluster = self.env.create_cluster(
            api=False, release_id=release.id)
        self.cluster.attributes.editable['provision']['method'] = \
            consts.PROVISION_METHODS.cobbler

        serialized_info = self.serializer.serialize(self.cluster, [])

        self.assertIn('pre_provision', serialized_info)
        self.assertTrue(filter(
            lambda task: all([
                task['uids'] == ['master'],
                task['type'] == 'shell',
                task['parameters']['cmd'].startswith(
                    'download-debian-installer')
            ]),
            serialized_info['pre_provision']))
        self.assertFalse(filter(
            lambda task: all([
                task['uids'] == ['master'],
                task['type'] == 'shell',
                task['parameters']['cmd'].startswith('fuel-image')
            ]),
            serialized_info['pre_provision']))

    def test_centos_prov_task_for_cobbler(self):
        release = self.env.create_release(
            api=False, operating_system=consts.RELEASE_OS.centos)
        self.cluster = self.env.create_cluster(
            api=False, release_id=release.id)
        self.cluster.attributes.editable['provision']['method'] = \
            consts.PROVISION_METHODS.cobbler

        serialized_info = self.serializer.serialize(self.cluster, [])

        self.assertIn('pre_provision', serialized_info)
        self.assertFalse(filter(
            lambda task: all([
                task['priority'] == 100,
                task['uids'] == ['master'],
                task['type'] == 'shell',
                task['parameters']['cmd'].startswith('fuel-image')
            ]),
            serialized_info['pre_provision']))
        self.assertIn('pre_provision', serialized_info)
        self.assertEquals([], serialized_info['pre_provision'])

    def test_centos_prov_task_for_images(self):
        release = self.env.create_release(
            api=False, operating_system=consts.RELEASE_OS.centos)
        self.cluster = self.env.create_cluster(
            api=False, release_id=release.id)
        self.cluster.attributes.editable['provision']['method'] = \
            consts.PROVISION_METHODS.image

        serialized_info = self.serializer.serialize(self.cluster, [])

        self.assertIn('pre_provision', serialized_info)
        self.assertFalse(filter(
            lambda task: all([
                task['priority'] == 100,
                task['uids'] == ['master'],
                task['type'] == 'shell',
                task['parameters']['cmd'].startswith('fuel-image')
            ]),
            serialized_info['pre_provision']))
        self.assertIn('pre_provision', serialized_info)
        self.assertEquals([], serialized_info['pre_provision'])

    def test_engine_does_not_contain_provisioning_method(self):
        self.cluster = self.env.create_cluster(api=False)
        serialized_info = self.serializer.serialize(self.cluster, [])

        self.assertNotIn('provision_method', serialized_info['engine'])
