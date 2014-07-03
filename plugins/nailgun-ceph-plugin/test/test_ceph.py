# -*- coding: utf-8 -*-

#    Copyright 2014 Mirantis, Inc.
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

from nailgun.errors import errors
from nailgun import objects

from nailgun.openstack.common import jsonutils
from nailgun.test.base import fake_tasks
from nailgun.test.base import reverse

from nailgun.test.base import BaseIntegrationTest

from nailgun.test.integration.test_orchestrator_serializer \
    import OrchestratorSerializerTestBase

from nailgun.test.unit.test_node_disks \
    import TestNodeVolumesInformationHandler
from nailgun.test.unit.test_node_disks \
    import TestVolumeManager


class TestCephNodeDisksHandlers(BaseIntegrationTest):

    def create_node(self, roles=None, pending_roles=None):
        if roles is None:
            roles = ['controller']
        if pending_roles is None:
            pending_roles = []
        self.env.create(
            nodes_kwargs=[{
                'roles': roles,
                'pending_roles': pending_roles,
                'pending_addition': True,
                'api': True}])

        return self.env.nodes[0]

    def get(self, node_id):
        resp = self.app.get(
            reverse('NodeDisksHandler', kwargs={'node_id': node_id}),
            headers=self.default_headers)

        self.assertEqual(200, resp.status_code)
        return jsonutils.loads(resp.body)

    def put(self, node_id, data, expect_errors=False):
        resp = self.app.put(
            reverse('NodeDisksHandler', kwargs={'node_id': node_id}),
            jsonutils.dumps(data),
            headers=self.default_headers,
            expect_errors=expect_errors)

        if not expect_errors:
            self.assertEqual(200, resp.status_code)
            return jsonutils.loads(resp.body)
        else:
            return resp

    def test_update_ceph_partition(self):
        node = self.create_node(roles=['ceph-osd'])
        disks = self.get(node.id)

        new_volume_size = 4321
        for disk in disks:
            if disk['size'] > 0:
                for volume in disk['volumes']:
                    volume['size'] = new_volume_size

        self.put(node.id, disks)
        partitions_after_update = filter(
            lambda volume: volume.get('type') == 'partition',
            objects.Node.get_volumes(node))

        for partition_after in partitions_after_update:
            self.assertEqual(partition_after['size'], new_volume_size)


class TestCephVolumeManager(TestVolumeManager):

    # from test_node_disks

    def test_multirole_controller_ceph(self):
        node = self.create_node('controller', 'ceph-osd')
        self.should_contain_os_with_minimal_size(
            objects.Node.get_volume_manager(node)
        )
        self.should_allocates_same_size(
            objects.Node.get_volume_manager(node).volumes, ['image', 'ceph'])
        self.logical_volume_sizes_should_equal_all_phisical_volumes(
            objects.Node.get_volumes(node))
        self.check_disk_size_equal_sum_of_all_volumes(
            objects.Node.get_volumes(node)
        )

    def test_check_volume_size_for_deployment(self):
        node = self.create_node('controller', 'ceph-osd')
        # First disk contains more than minimum size of all VGs
        self.update_node_with_single_disk(node, 116384)
        # Second is taken entirely by ceph
        self.add_disk_to_node(node, 65536)
        objects.Node.get_volume_manager(
            node
        ).check_volume_sizes_for_deployment()

        # First disk contains less than minimum size of all VGs
        self.update_node_with_single_disk(node, 16384)

        # Second is taken entirely by ceph
        self.add_disk_to_node(node, 65536)

        self.assertRaises(
            errors.NotEnoughFreeSpace,
            objects.Node.get_volume_manager(
                node
            ).check_volume_sizes_for_deployment
        )

    def test_multirole_controller_cinder_ceph(self):
        node = self.create_node('controller', 'cinder', 'ceph-osd')
        self.should_contain_os_with_minimal_size(
            objects.Node.get_volume_manager(node)
        )
        self.should_allocates_same_size(
            objects.Node.get_volume_manager(node).volumes,
            ['image', 'cinder', 'ceph']
        )
        self.logical_volume_sizes_should_equal_all_phisical_volumes(
            objects.Node.get_volumes(node))
        self.check_disk_size_equal_sum_of_all_volumes(
            objects.Node.get_volumes(node)
        )

    def test_allocates_space_single_disk_for_ceph_for_ceph_role(self):
        node = self.create_node('ceph-osd')
        self.update_node_with_single_disk(node, 30000)
        self.should_contain_os_with_minimal_size(
            objects.Node.get_volume_manager(node)
        )
        self.all_free_space_except_os_for_volume(
            objects.Node.get_volume_manager(node).volumes, 'ceph')
        self.check_disk_size_equal_sum_of_all_volumes(
            objects.Node.get_volumes(node)
        )

    def test_allocates_full_disks_for_ceph_for_ceph_role(self):
        node = self.create_node('ceph-osd')
        self.should_contain_os_with_minimal_size(
            objects.Node.get_volume_manager(node)
        )
        self.all_free_space_except_os_disks_for_volume(
            objects.Node.get_volume_manager(node), 'ceph')


class TestCephVolumeInformation(TestNodeVolumesInformationHandler):

    def test_volumes_information_for_ceph_role(self):
        node_db = self.create_node('ceph-osd')
        response = self.get(node_db.id)
        self.check_volumes(response, ['os', 'ceph', 'cephjournal'])

    # /from test_node_disks
    # from test_cluster_changes_handler

    def test_occurs_error_not_enough_osds_for_ceph(self):
        cluster = self.env.create(
            nodes_kwargs=[
                {'roles': ['controller', 'ceph-osd'],
                 'pending_addition': True}])

        self.app.patch(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster['id']}),
            params=jsonutils.dumps({
                'editable': {
                    'storage': {'volumes_ceph': {'value': True},
                                'osd_pool_size': {'value': 3}}}}),
            headers=self.default_headers)

        task = self.env.launch_deployment()

        self.assertEqual(task.status, 'error')
        self.assertEqual(
            task.message,
            'Number of OSD nodes (1) cannot be less than '
            'the Ceph object replication factor (3). '
            'Please either assign ceph-osd role to more nodes, '
            'or reduce Ceph replication factor in the Settings tab.')

    @fake_tasks(godmode=True)
    def test_enough_osds_for_ceph(self):
        cluster = self.env.create(
            nodes_kwargs=[
                {'roles': ['controller', 'ceph-osd'],
                 'pending_addition': True}])
        self.app.patch(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster['id']}),
            params=jsonutils.dumps({
                'editable': {
                    'storage': {'volumes_ceph': {'value': True},
                                'osd_pool_size': {'value': 1}}}}),
            headers=self.default_headers)

        task = self.env.launch_deployment()
        self.assertIn(task.status, ('running', 'ready'))

    # /from test_cluster_changes_handler
    # from test_volume_manager

    def test_no_glance_partition_when_ceph_used_for_images(self):
        """Verifies that no partition with id image is not present when
        images_ceph used
        """
        cluster = self.env.create(
            cluster_kwargs={
                'mode': 'multinode'},
            nodes_kwargs=[
                {'roles': ['controller', 'ceph-osd']}])
        self.app.patch(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster['id']}),
            params=jsonutils.dumps({
                'editable': {'storage': {'images_ceph': {'value': True}}}}),
            headers=self.default_headers)
        volumes = objects.Node.get_volume_manager(
            self.env.nodes[0]
        ).gen_volumes_info()

        image_volume = next((v for v in volumes if v['id'] == 'image'), None)
        self.assertIsNone(image_volume)

    def test_glance_partition_without_ceph_osd(self):
        self.env.create(
            cluster_kwargs={
                'mode': 'multinode'},
            nodes_kwargs=[
                {'roles': ['controller']}])
        volumes = objects.Node.get_volume_manager(
            self.env.nodes[0]
        ).gen_volumes_info()

        image_volume = next((v for v in volumes if v['id'] == 'image'), None)
        self.assertIsNotNone(image_volume)
        self.assertEqual(len(image_volume['volumes']), 1)
        self.assertEqual(image_volume['volumes'][0]['mount'],
                         '/var/lib/glance')

    # /from test_volume_manager
    # from test_orchestrator_serializer


class TestCephOsdImageOrchestratorSerialize(OrchestratorSerializerTestBase):

    def setUp(self):
        super(TestCephOsdImageOrchestratorSerialize, self).setUp()
        cluster = self.env.create(
            cluster_kwargs={
                'mode': 'multinode'},
            nodes_kwargs=[
                {'roles': ['controller', 'ceph-osd']}])
        self.app.patch(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster['id']}),
            params=jsonutils.dumps({
                'editable': {'storage': {'images_ceph': {'value': True}}}}),
            headers=self.default_headers)
        self.cluster = objects.Cluster.get_by_uid(cluster['id'])

    def test_glance_image_cache_max_size(self):
        data = self.serialize(self.cluster)
        self.assertEqual(len(data), 2)
        # one node - 2 roles
        self.assertEqual(data[0]['uid'], data[1]['uid'])
        self.assertEqual(data[0]['glance']['image_cache_max_size'], '0')
        self.assertEqual(data[1]['glance']['image_cache_max_size'], '0')


class TestCephPgNumOrchestratorSerialize(OrchestratorSerializerTestBase):

    def create_env(self, nodes, osd_pool_size='2'):
        cluster = self.env.create(
            cluster_kwargs={
                'mode': 'multinode'},
            nodes_kwargs=nodes)
        self.app.patch(
            reverse(
                'ClusterAttributesHandler',
                kwargs={'cluster_id': cluster['id']}),
            params=jsonutils.dumps(
                {'editable': {
                    'storage': {
                        'osd_pool_size': {'value': osd_pool_size}}}}),
            headers=self.default_headers)
        return objects.Cluster.get_by_uid(cluster['id'])

    def test_pg_num_no_osd_nodes(self):
        cluster = self.create_env([
            {'roles': ['controller']}])
        data = self.serialize(cluster)
        self.assertEqual(data[0]['storage']['pg_num'], 128)

    def test_pg_num_1_osd_node(self):
        cluster = self.create_env([
            {'roles': ['controller', 'ceph-osd']}])
        data = self.serialize(cluster)
        self.assertEqual(data[0]['storage']['pg_num'], 256)

    def test_pg_num_1_osd_node_repl_4(self):
        cluster = self.create_env(
            [{'roles': ['controller', 'ceph-osd']}],
            '4')
        data = self.serialize(cluster)
        self.assertEqual(data[0]['storage']['pg_num'], 128)

    def test_pg_num_3_osd_nodes(self):
        cluster = self.create_env([
            {'roles': ['controller', 'ceph-osd']},
            {'roles': ['compute', 'ceph-osd']},
            {'roles': ['compute', 'ceph-osd']}])
        data = self.serialize(cluster)
        self.assertEqual(data[0]['storage']['pg_num'], 512)
