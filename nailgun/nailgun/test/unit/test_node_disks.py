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

from copy import deepcopy
from mock import patch
import string

from nailgun.errors import errors
from nailgun.openstack.common import jsonutils
from nailgun.test.base import BaseIntegrationTest
from nailgun.test.base import fake_tasks
from nailgun.test.base import reverse
from nailgun.volumes.manager import Disk
from nailgun.volumes.manager import DisksFormatConvertor
from nailgun.volumes.manager import only_disks
from nailgun.volumes.manager import only_vg


class TestNodeDisksHandlers(BaseIntegrationTest):

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

    @staticmethod
    def get_vgs(resp):
        disks_vgs = [d['volumes'] for d in resp]
        vgs = [vg['name'] for disk_vgs in disks_vgs for vg in disk_vgs]
        return set(vgs)

    @fake_tasks()
    def test_clean_volumes_after_reset(self):
        disks = [
            {
                "model": "TOSHIBA MK1002TS",
                "name": "sda",
                "disk": "sda",
                "size": 1000204886016
            },
            {
                "model": "TOSHIBA MK1002TS",
                "name": "sdb",
                "disk": "disk/by-path/pci-0000:00:0d.0-scsi-0:0:0:0",
                "size": 1000204886016
            },
        ]
        self.env.create(
            nodes_kwargs=[{
                "roles": [],
                "pending_roles": ['compute'],
                "meta": {"disks": disks}
            }]
        )
        self.env.launch_deployment()
        self.env.reset_environment()

        node_db = self.env.nodes[0]

        # simulate disk change
        new_meta = deepcopy(node_db.meta)
        new_meta['disks'][0]['disk'] = new_meta['disks'][1]['disk']
        new_meta['disks'][1]['disk'] = 'sdb'
        node_db.meta = new_meta
        self.env.db.commit()

        # check that we can config disks after reset
        disks = self.get(node_db.id)
        disks[0]['volumes'][0]['size'] -= 100
        updated_disks = self.put(node_db.id, disks)

        self.assertEqual(disks, updated_disks)

    def test_default_attrs_after_creation(self):
        self.env.create_node(api=True)
        node_db = self.env.nodes[0]
        disks = self.get(node_db.id)

        self.assertGreater(len(disks), 0)
        for disk in disks:
            self.assertTrue(type(disk['size']) == int)
            self.assertGreaterEqual(disk['size'], 0)
            self.assertEqual(len(disk['volumes']), 0)

    def test_volumes_regeneration_after_roles_update(self):
        self.env.create(
            nodes_kwargs=[
                {"roles": [], "pending_roles": ['compute']}
            ]
        )
        node_db = self.env.nodes[0]
        original_roles_response = self.get(node_db.id)

        def update_node_roles(roles):
            resp = self.app.put(
                reverse('NodeCollectionHandler'),
                jsonutils.dumps([{'id': node_db.id, 'pending_roles': roles}]),
                headers=self.default_headers)
            self.assertEqual(200, resp.status_code)

        # adding role
        update_node_roles(['compute', 'cinder'])
        modified_roles_response = self.get(node_db.id)
        self.assertNotEqual(self.get_vgs(original_roles_response),
                            self.get_vgs(modified_roles_response))
        original_roles_response = modified_roles_response

        # replacing role
        update_node_roles(['compute', 'ceph-osd'])
        modified_roles_response = self.get(node_db.id)
        self.assertNotEqual(self.get_vgs(original_roles_response),
                            self.get_vgs(modified_roles_response))
        original_roles_response = modified_roles_response

        # removing role
        update_node_roles(['compute'])
        modified_roles_response = self.get(node_db.id)
        self.assertNotEqual(self.get_vgs(original_roles_response),
                            self.get_vgs(modified_roles_response))
        original_roles_response = modified_roles_response

        # replacing role to itself
        update_node_roles(['controller'])
        update_node_roles(['compute'])
        modified_roles_response = self.get(node_db.id)
        self.assertEqual(self.get_vgs(original_roles_response),
                         self.get_vgs(modified_roles_response))

    def test_volumes_update_after_roles_assignment(self):
        self.env.create(
            nodes_kwargs=[
                {"cluster_id": None}
            ]
        )
        node_db = self.env.nodes[0]
        original_roles_response = self.get(node_db.id)

        # adding role
        assignment_data = [
            {
                "id": node_db.id,
                "roles": ['compute', 'cinder']
            }
        ]
        self.app.post(
            reverse(
                'NodeAssignmentHandler',
                kwargs={'cluster_id': self.env.clusters[0].id}
            ),
            jsonutils.dumps(assignment_data),
            headers=self.default_headers
        )

        modified_roles_response = self.get(node_db.id)
        self.assertNotEqual(self.get_vgs(original_roles_response),
                            self.get_vgs(modified_roles_response))

    def test_disks_volumes_size_update(self):
        node_db = self.create_node()
        disks = self.get(node_db.id)
        for disk in disks:
            if disk['size'] > 0:
                for volume in disk['volumes']:
                    volume['size'] = 4200
        expect_disks = deepcopy(disks)

        response = self.put(node_db.id, disks)
        self.assertEqual(response, expect_disks)

        response = self.get(node_db.id)
        self.assertEqual(response, expect_disks)

    def test_os_vg_one_disk_ubuntu(self):
        self.env.create(
            release_kwargs={
                "operating_system": "Ubuntu"
            },
            nodes_kwargs=[
                {"roles": [], "pending_roles": ['controller']}
            ]
        )
        node_db = self.env.nodes[0]
        disks = self.get(node_db.id)
        for disk in disks:
            for vol in disk["volumes"]:
                if disk["size"] > 100:
                    vol["size"] = 100 if vol["name"] == "os" else 0
        resp = self.put(node_db.id, disks, expect_errors=True)
        self.assertEqual(
            resp.body,
            "Base system should be allocated on one disk only"
        )

    def test_recalculates_vg_sizes_when_disks_volumes_size_update(self):
        node_db = self.create_node()
        disks = self.get(node_db.id)

        vgs_before_update = filter(
            lambda volume: volume.get('type') == 'vg',
            node_db.attributes.volumes)

        new_volume_size = 4200
        updated_disks_count = 0
        for disk in disks:
            if disk['size'] > 0:
                for volume in disk['volumes']:
                    volume['size'] = new_volume_size
                updated_disks_count += 1

        self.put(node_db.id, disks)

        vgs_after_update = filter(
            lambda volume: volume.get('type') == 'vg',
            node_db.attributes.volumes)

        for vg_before, vg_after in zip(vgs_before_update, vgs_after_update):
            size_volumes_before = sum([
                volume.get('size', 0) for volume in vg_before['volumes']])
            size_volumes_after = sum([
                volume.get('size', 0) for volume in vg_after['volumes']])

            self.assertNotEqual(size_volumes_before, size_volumes_after)

            volume_group_size = new_volume_size * updated_disks_count
            self.assertEqual(size_volumes_after, volume_group_size)

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
            node.attributes.volumes)

        for partition_after in partitions_after_update:
            self.assertEqual(partition_after['size'], new_volume_size)

    def test_validator_at_least_one_disk_exists(self):
        node = self.create_node()
        response = self.put(node.id, [], True)
        self.assertEqual(response.status_code, 400)
        self.assertRegexpMatches(response.body,
                                 '^Node seems not to have disks')

    def test_validator_not_enough_size_for_volumes(self):
        node = self.create_node()
        disks = self.get(node.id)

        for disk in disks:
            if disk['size'] > 0:
                for volume in disk['volumes']:
                    volume['size'] = disk['size'] + 1

        response = self.put(node.id, disks, True)
        self.assertEqual(response.status_code, 400)
        self.assertRegexpMatches(
            response.body, '^Not enough free space on disk: .+')

    def test_validator_invalid_data(self):
        node = self.create_node()
        disks = self.get(node.id)

        for disk in disks:
            for volume in disk['volumes']:
                del volume['size']

        response = self.put(node.id, disks, True)
        self.assertEqual(response.status_code, 400)
        self.assertRegexpMatches(
            response.body, "'size' is a required property")


class TestNodeDefaultsDisksHandler(BaseIntegrationTest):

    def get(self, node_id):
        resp = self.app.get(
            reverse('NodeDefaultsDisksHandler', kwargs={'node_id': node_id}),
            headers=self.default_headers)

        self.assertEqual(200, resp.status_code)
        return jsonutils.loads(resp.body)

    def test_node_disk_amount_regenerates_volumes_info_if_new_disk_added(self):
        cluster = self.env.create_cluster(api=True)
        self.env.create_node(
            api=True,
            roles=['compute'],  # vgs: os, vm
            cluster_id=cluster['id'])
        node_db = self.env.nodes[0]
        response = self.get(node_db.id)
        self.assertEqual(len(response), 6)

        new_meta = node_db.meta.copy()
        new_meta['disks'].append({
            'size': 1000022933376,
            'model': 'SAMSUNG B00B135',
            'name': 'sda',
            'disk': 'disk/id/b00b135'})

        self.app.put(
            reverse('NodeAgentHandler'),
            jsonutils.dumps({
                "mac": node_db.mac,
                "meta": new_meta}),
            headers=self.default_headers)

        self.env.refresh_nodes()

        response = self.get(node_db.id)
        self.assertEqual(len(response), 7)

        # check all groups on all disks
        vgs = ['os', 'vm']
        for disk in response:
            self.assertEqual(len(disk['volumes']), len(vgs))

    def test_get_default_attrs(self):
        self.env.create_node(api=True)
        node_db = self.env.nodes[0]
        volumes_from_api = self.get(node_db.id)

        default_volumes = node_db.volume_manager.gen_volumes_info()
        disks = only_disks(default_volumes)

        self.assertEqual(len(disks), len(volumes_from_api))


class TestNodeVolumesInformationHandler(BaseIntegrationTest):

    def get(self, node_id):
        resp = self.app.get(
            reverse('NodeVolumesInformationHandler',
                    kwargs={'node_id': node_id}),
            headers=self.default_headers)

        self.assertEqual(200, resp.status_code)
        return jsonutils.loads(resp.body)

    def create_node(self, role):
        self.env.create(
            nodes_kwargs=[{'roles': [role], 'pending_addition': True}])

        return self.env.nodes[0]

    def check_volumes(self, volumes, volumes_ids):
        self.assertEqual(len(volumes), len(volumes_ids))
        for volume_id in volumes_ids:
            # Volume has name
            volume = filter(
                lambda volume: volume['name'] == volume_id, volumes)[0]
            # min_size
            self.assertTrue(type(volume['min_size']) == int)
            self.assertGreaterEqual(volume['min_size'], 0)
            # and label
            self.assertTrue(type(volume['label']) in (str, unicode))
            self.assertGreater(volume['label'], 0)

    def test_volumes_information_for_cinder_role(self):
        node_db = self.create_node('cinder')
        response = self.get(node_db.id)
        self.check_volumes(response, ['os', 'cinder'])

    def test_volumes_information_for_compute_role(self):
        node_db = self.create_node('compute')
        response = self.get(node_db.id)
        self.check_volumes(response, ['os', 'vm'])

    def test_volumes_information_for_controller_role(self):
        node_db = self.create_node('controller')
        response = self.get(node_db.id)
        self.check_volumes(response, ['os', 'image'])

    def test_volumes_information_for_ceph_role(self):
        node_db = self.create_node('ceph-osd')
        response = self.get(node_db.id)
        self.check_volumes(response, ['os', 'ceph', 'cephjournal'])


class TestVolumeManager(BaseIntegrationTest):

    def create_node(self, *roles):
        self.env.create(
            nodes_kwargs=[{
                'roles': [],
                'pending_roles': roles,
                'pending_addition': True,
                'api': True}])

        return self.env.nodes[-1]

    def non_zero_size(self, size):
        self.assertTrue(type(size) == int)
        self.assertGreater(size, 0)

    def os_size(self, disks, with_lvm_meta=True):
        os_sum_size = 0
        for disk in only_disks(disks):
            os_volume = filter(
                lambda volume: volume.get('vg') == 'os', disk['volumes'])[0]
            os_sum_size += os_volume['size']
            if not with_lvm_meta:
                os_sum_size -= os_volume['lvm_meta_size']

        self.non_zero_size(os_sum_size)
        return os_sum_size

    def glance_size(self, disks):
        glance_sum_size = 0
        for disk in only_disks(disks):
            glance_volume = filter(
                lambda volume: volume.get('vg') == 'image', disk['volumes']
            )[0]
            glance_sum_size += glance_volume['size']

        self.non_zero_size(glance_sum_size)
        return glance_sum_size

    def reserved_size(self, spaces):
        reserved_size = 0
        for disk in only_disks(spaces):
            reserved_size += DisksFormatConvertor.\
                calculate_service_partitions_size(disk['volumes'])

        return reserved_size

    def should_contain_os_with_minimal_size(self, volume_manager):
        self.assertEqual(
            self.os_size(volume_manager.volumes, with_lvm_meta=False),
            volume_manager.call_generator('calc_min_os_size'))

    def all_free_space_except_os_for_volume(self, spaces, volume_name):
        os_size = self.os_size(spaces)
        reserved_size = self.reserved_size(spaces)
        disk_sum_size = sum([disk['size'] for disk in only_disks(spaces)])
        vg_size = 0
        sum_lvm_meta = 0
        for disk in only_disks(spaces):
            for volume in disk['volumes']:
                if volume.get('vg') == volume_name or \
                   volume.get('name') == volume_name:
                    vg_size += volume['size']
                    vg_size -= volume.get('lvm_meta_size', 0)
                    sum_lvm_meta += volume.get('lvm_meta_size', 0)

        self.assertEqual(
            vg_size, disk_sum_size - os_size - reserved_size - sum_lvm_meta)

    def all_free_space_except_os_disks_for_volume(self, volume_manager,
                                                  volume_name):
        spaces = volume_manager.volumes
        reserved_size = self.reserved_size(spaces)
        disk_sum_size = sum([disk['size'] for disk in only_disks(spaces)])
        boot_data_size = volume_manager.call_generator('calc_boot_size') + \
            volume_manager.call_generator('calc_boot_records_size')
        vg_size = 0
        sum_lvm_meta = 0

        for disk in only_disks(spaces):
            for volume in disk['volumes']:
                # Exclude disks with OS vg as Ceph won't be there
                if volume.get('vg') == 'os' and volume.get('size', 0) > 0:
                    disk_sum_size -= (disk['size'] - boot_data_size)
                if volume.get('vg') == volume_name or \
                   volume.get('name') == volume_name:
                    vg_size += volume['size']
                    vg_size -= volume.get('lvm_meta_size', 0)
                    sum_lvm_meta += volume.get('lvm_meta_size', 0)

        self.assertEqual(
            vg_size, disk_sum_size - reserved_size - sum_lvm_meta)

    def logical_volume_sizes_should_equal_all_phisical_volumes(self, spaces):
        vg_sizes = {}
        for vg in only_vg(spaces):
            for volume in vg['volumes']:
                vg_name = vg['id']
                if not vg_sizes.get(vg_name):
                    vg_sizes[vg_name] = 0
                vg_sizes[vg_name] += volume['size']

        pv_sizes = {}
        for disk in only_disks(spaces):
            for volume in disk['volumes']:
                # Skip cinder because it does not have
                # logical volumes
                if volume.get('vg') == 'cinder':
                    continue

                if volume['type'] == 'pv':
                    vg_name = volume['vg']
                    if not pv_sizes.get(vg_name):
                        pv_sizes[vg_name] = 0

                    pv_sizes[vg_name] += volume['size']
                    pv_sizes[vg_name] -= volume['lvm_meta_size']

        self.assertEqual(vg_sizes, pv_sizes)

    def check_disk_size_equal_sum_of_all_volumes(self, spaces):
        for disk in only_disks(spaces):
            volumes_size = sum(
                [volume.get('size', 0) for volume in disk['volumes']])

            self.assertEqual(volumes_size, disk['size'])

    def test_volume_request_without_cluster(self):
        self.env.create_node(api=True)
        node = self.env.nodes[-1]
        resp = self.app.get(
            reverse('NodeVolumesInformationHandler',
                    kwargs={'node_id': node.id}),
            headers=self.default_headers,
            expect_errors=True
        )
        self.assertEqual(404, resp.status_code)

    def test_allocates_all_free_space_for_os_for_controller_role(self):
        node = self.create_node('controller')
        disks = only_disks(node.volume_manager.volumes)
        disks_size_sum = sum([disk['size'] for disk in disks])
        os_sum_size = self.os_size(disks)
        glance_sum_size = self.glance_size(disks)
        reserved_size = self.reserved_size(disks)

        self.assertEqual(disks_size_sum - reserved_size,
                         os_sum_size + glance_sum_size)
        self.logical_volume_sizes_should_equal_all_phisical_volumes(
            node.attributes.volumes)
        self.check_disk_size_equal_sum_of_all_volumes(node.attributes.volumes)

    def test_allocates_all_free_space_for_vm_for_compute_role(self):
        node = self.create_node('compute')
        self.should_contain_os_with_minimal_size(node.volume_manager)
        self.all_free_space_except_os_for_volume(
            node.volume_manager.volumes, 'vm')
        self.logical_volume_sizes_should_equal_all_phisical_volumes(
            node.attributes.volumes)
        self.check_disk_size_equal_sum_of_all_volumes(node.attributes.volumes)

    def test_allocates_all_free_space_for_vm_for_cinder_role(self):
        node = self.create_node('cinder')
        self.should_contain_os_with_minimal_size(node.volume_manager)
        self.all_free_space_except_os_for_volume(
            node.volume_manager.volumes, 'cinder')
        self.check_disk_size_equal_sum_of_all_volumes(node.attributes.volumes)

    def test_allocates_space_single_disk_for_ceph_for_ceph_role(self):
        node = self.create_node('ceph-osd')
        self.update_node_with_single_disk(node, 30000)
        self.should_contain_os_with_minimal_size(node.volume_manager)
        self.all_free_space_except_os_for_volume(
            node.volume_manager.volumes, 'ceph')
        self.check_disk_size_equal_sum_of_all_volumes(node.attributes.volumes)

    def test_allocates_full_disks_for_ceph_for_ceph_role(self):
        node = self.create_node('ceph-osd')
        self.should_contain_os_with_minimal_size(node.volume_manager)
        self.all_free_space_except_os_disks_for_volume(
            node.volume_manager, 'ceph')

    def should_allocates_same_size(self, volumes, same_size_volume_names):
        disks = only_disks(volumes)

        actual_volumes_size = {}
        for disk in disks:
            for volume in disk['volumes']:
                name = volume.get('vg') or volume.get('name')
                if not name:
                    continue
                actual_volumes_size.setdefault(name, {})
                actual_volumes_size[name].setdefault('size', 0)
                actual_volumes_size[name].setdefault(
                    'type', volume.get('type'))
                actual_volumes_size[name]['size'] += volume.get('size')

        actual_volumes = [v for k, v in actual_volumes_size.iteritems()
                          if k in same_size_volume_names]

        # All pv should have equal size
        actual_pv_volumes = filter(
            lambda volume: volume['type'] == 'pv', actual_volumes)
        sum_pv_size = sum([volume['size'] for volume in actual_pv_volumes])
        average_size = sum_pv_size / len(actual_pv_volumes)
        for pv in actual_pv_volumes:
            # In cases where all volumes are created on one disk and
            # that disk has an odd-numbered size the volume sizes will
            # differ by 1.
            self.assertAlmostEqual(pv['size'], average_size, delta=1)

    def test_multirole_controller_ceph(self):
        node = self.create_node('controller', 'ceph-osd')
        self.should_contain_os_with_minimal_size(node.volume_manager)
        self.should_allocates_same_size(
            node.volume_manager.volumes, ['image', 'ceph'])
        self.logical_volume_sizes_should_equal_all_phisical_volumes(
            node.attributes.volumes)
        self.check_disk_size_equal_sum_of_all_volumes(node.attributes.volumes)

    def test_multirole_controller_cinder_ceph(self):
        node = self.create_node('controller', 'cinder', 'ceph-osd')
        self.should_contain_os_with_minimal_size(node.volume_manager)
        self.should_allocates_same_size(
            node.volume_manager.volumes, ['image', 'cinder', 'ceph'])
        self.logical_volume_sizes_should_equal_all_phisical_volumes(
            node.attributes.volumes)
        self.check_disk_size_equal_sum_of_all_volumes(node.attributes.volumes)

    def create_node_and_calculate_min_size(
            self, role, space_info, volumes_metadata):
        node = self.create_node(role)
        volume_manager = node.volume_manager
        min_installation_size = self.__calc_minimal_installation_size(
            volume_manager
        )
        return node, min_installation_size

    def update_node_with_single_disk(self, node, size):
        new_meta = node.meta.copy()
        new_meta['disks'] = [{
            # convert mbytes to bytes
            'size': size * (1024 ** 2),
            'model': 'SAMSUNG B00B135',
            'name': 'sda',
            'disk': 'disk/id/a00b135'}]

        self.app.put(
            reverse('NodeAgentHandler'),
            jsonutils.dumps({
                'mac': node.mac,
                'meta': new_meta}),
            headers=self.default_headers)

    def add_disk_to_node(self, node, size):
        new_meta = node.meta.copy()
        last_disk = [d['name'][-1] for d in new_meta['disks']][-1]
        new_disk = string.letters.index(last_disk) + 1

        new_meta['disks'].append({
            # convert mbytes to bytes
            'size': size * (1024 ** 2),
            'model': 'SAMSUNG B00B135',
            'name': 'sd%s' % string.letters[new_disk],
            'disk': 'disk/id/%s00b135' % string.letters[new_disk]})

        self.app.put(
            reverse('NodeAgentHandler'),
            jsonutils.dumps({
                'mac': node.mac,
                'meta': new_meta}),
            headers=self.default_headers)

    def test_check_disk_space_for_deployment(self):
        min_size = 100000

        volumes_metadata = self.env.get_default_volumes_metadata()
        volumes_roles_mapping = volumes_metadata['volumes_roles_mapping']

        for role, space_info in volumes_roles_mapping.iteritems():
            node, min_installation_size = self.\
                create_node_and_calculate_min_size(
                    role, space_info, volumes_metadata)

            self.update_node_with_single_disk(node, min_size)
            vm = node.volume_manager
            with patch.object(vm,
                              '_VolumeManager'
                              '__calc_minimal_installation_size',
                              return_value=min_size):
                vm.check_disk_space_for_deployment()

            self.update_node_with_single_disk(node, min_size - 1)
            vm = node.volume_manager
            with patch.object(vm,
                              '_VolumeManager'
                              '__calc_minimal_installation_size',
                              return_value=min_size):
                self.assertRaises(
                    errors.NotEnoughFreeSpace,
                    vm.check_disk_space_for_deployment
                )

    def test_calc_minimal_installation_size(self):
        volumes_metadata = self.env.get_default_volumes_metadata()
        volumes_roles_mapping = volumes_metadata['volumes_roles_mapping']

        for role, space_info in volumes_roles_mapping.iteritems():
            node = self.create_node(role)
            vm = node.volume_manager
            self.assertEqual(
                vm._VolumeManager__calc_minimal_installation_size(),
                self.__calc_minimal_installation_size(vm)
            )

    def __calc_minimal_installation_size(self, volume_manager):
        disks_count = len(filter(lambda disk: disk.size > 0,
                                 volume_manager.disks))
        boot_size = volume_manager.call_generator('calc_boot_size') + \
            volume_manager.call_generator('calc_boot_records_size')

        min_installation_size = disks_count * boot_size
        for volume in volume_manager.allowed_volumes:
            min_size = volume_manager.expand_generators(volume)['min_size']
            min_installation_size += min_size
        return min_installation_size

    def test_check_volume_size_for_deployment(self):
        node = self.create_node('controller', 'ceph-osd')
        # First disk contains more than minimum size of all VGs
        self.update_node_with_single_disk(node, 116384)
        # Second is taken entirely by ceph
        self.add_disk_to_node(node, 65536)
        node.volume_manager.check_volume_sizes_for_deployment()

        # First disk contains less than minimum size of all VGs
        self.update_node_with_single_disk(node, 16384)
        # Second is taken entirely by ceph
        self.add_disk_to_node(node, 65536)
        self.assertRaises(
            errors.NotEnoughFreeSpace,
            node.volume_manager.check_volume_sizes_for_deployment)

    def update_ram_and_assert_swap_size(self, node, size, swap_size):
        new_meta = deepcopy(node.meta)
        new_meta['memory']['total'] = (1024 ** 2) * size
        node.meta = new_meta
        self.env.db.commit()
        self.assertEqual(node.volume_manager._calc_swap_size(), swap_size)

    def test_root_size_calculation(self):
        node = self.create_node('controller')

        self.update_ram_and_assert_swap_size(node, 2, 4)

        self.update_ram_and_assert_swap_size(node, 2048, 4096)
        self.update_ram_and_assert_swap_size(node, 2049, 2049)

        self.update_ram_and_assert_swap_size(node, 8192, 8192)
        self.update_ram_and_assert_swap_size(node, 8193, 4096)

        self.update_ram_and_assert_swap_size(node, 65536, 32768)
        self.update_ram_and_assert_swap_size(node, 65537, 4096)

        self.update_ram_and_assert_swap_size(node, 81920, 4096)


class TestDisks(BaseIntegrationTest):

    def get_boot(self, volumes):
        return filter(
            lambda volume: volume.get('mount') == '/boot',
            volumes)[0]

    def create_disk(self, boot_is_raid=False, possible_pvs_count=0):
        return Disk(
            [], lambda name: 100, 'sda', 'sda', 10000,
            boot_is_raid=boot_is_raid, possible_pvs_count=possible_pvs_count)

    def test_create_mbr_as_raid_if_disks_count_greater_than_zero(self):
        disk = self.create_disk(boot_is_raid=True)
        boot_partition = self.get_boot(disk.volumes)
        self.assertEqual(boot_partition['type'], 'raid')

    def test_create_mbr_as_partition_if_disks_count_less_than_zero(self):
        disk = self.create_disk()
        boot_partition = self.get_boot(disk.volumes)
        self.assertEqual(boot_partition['type'], 'partition')

    def test_remove_pv(self):
        disk = self.create_disk(possible_pvs_count=1)
        disk_without_pv = deepcopy(disk)
        disk.create_pv({'id': 'pv_name'}, 100)
        disk.remove_pv('pv_name')

        self.assertEqual(disk_without_pv.render(), disk.render())

    def test_boot_partition_has_file_system(self):
        disk = self.create_disk(possible_pvs_count=1)
        boot_record = filter(
            lambda volume: volume.get('mount') == '/boot', disk.volumes)[0]
        self.assertEqual(boot_record['file_system'], 'ext2')


class TestFixtures(BaseIntegrationTest):

    @property
    def get_vgs_for_releases(self):
        openstack = self.env.read_fixtures(
            ('openstack',))[0]['fields']['volumes_metadata']['volumes']

        return [only_vg(openstack)]

    def test_each_logical_volume_has_file_system(self):
        for release_vgs in self.get_vgs_for_releases:
            for vg in release_vgs:
                for volume in vg['volumes']:
                    self.assertIn(
                        volume['file_system'],
                        ('ext2', 'ext4', 'swap', 'xfs', None))
