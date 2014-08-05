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

'''
Classes for working with disks and volumes.
All sizes in megabytes.
'''

from copy import deepcopy
from functools import partial
from nailgun.errors import errors
from nailgun.logger import logger
from nailgun.openstack.common import jsonutils


def is_service(space):
    '''Helper to check if the space is a service partition
    '''
    return (space.get('mount') == '/boot' or
            space.get('type') not in ('pv', 'partition', 'raid'))


def only_disks(spaces):
    '''Helper for retrieving only disks from spaces
    '''
    return filter(lambda space: space['type'] == 'disk', spaces)


def only_vg(spaces):
    '''Helper for retrieving only volumes groups from spaces
    '''
    return filter(lambda space: space['type'] == 'vg', spaces)


def gb_to_mb(gb):
    '''Convert gigabytes to megabytes
    '''
    return int(gb * 1024)


def byte_to_megabyte(byte):
    '''Convert bytes to megabytes
    '''
    return byte / 1024 ** 2


def mb_to_byte(mb):
    return mb * 1024 * 1024


def gb_to_byte(gb):
    return gb * 1024 * 1024 * 1024


def find_space_by_id(spaces, space_id):
    """Iterate through spaces and return space which has space_id."""
    return filter(lambda space: space.get('id') == space_id, spaces)[0]


def get_allocate_size(node, vol):
    """Determine 'allocate_size' value for a given volume
    """
    if len(node.meta['disks']) == 1 and vol['allocate_size'] == 'full-disk':
        return 'all'
    else:
        return vol['allocate_size']


def exclude_glance_partition(role_mapping, node):
    """In case images_ceph used as glance image storage
    no need to create partition /var/lib/glance
    """
    if node.cluster.attributes.editable['storage'].get('images_ceph'):
        images_ceph = (node.cluster.attributes['editable']['storage']
                       ['images_ceph']['value'])
        if images_ceph:
            # just filter out image volume
            role_mapping['controller'] = \
                filter(lambda space: space['id'] != 'image',
                       role_mapping['controller'])
    return


def modify_volumes_hook(role_mapping, node):
    """Filter node volumes based on filter functions logic
    """
    filters = [exclude_glance_partition]

    for f in filters:
        f(role_mapping, node)
    return role_mapping


def get_node_spaces(node):
    """Helper for retrieving node volumes.
    If spaces don't defained for role, will be used
    partitioning for role `other`.
    Sets key `_allocate_size` which used only for internal calculation
    and not used in partitioning system.
    """
    node_spaces = []

    role_mapping = node.cluster.release.volumes_metadata[
        'volumes_roles_mapping']

    # TODO(dshulyak)
    # This logic should go to openstack.yaml (or other template)
    # when it will be extended with flexible template engine
    modify_volumes_hook(role_mapping, node)
    all_spaces = node.cluster.release.volumes_metadata['volumes']

    for role in node.all_roles:
        if not role_mapping.get(role):
            continue
        volumes = role_mapping[role]

        for volume in volumes:
            space = find_space_by_id(all_spaces, volume['id'])
            if space not in node_spaces:
                space['_allocate_size'] = get_allocate_size(node, volume)
                node_spaces.append(space)

    # Use role `other`
    if not node_spaces:
        logger.warn('Cannot find volumes for node: %s assigning default '
                    'volumes' % (node.full_name))
        for volume in role_mapping['other']:
            space = find_space_by_id(all_spaces, volume['id'])
            space['_allocate_size'] = get_allocate_size(node, volume)
            node_spaces.append(space)

    return node_spaces


def calc_glance_cache_size(volumes):
    """Calculate glance cache size based on formula:
    10%*(/var/lib/glance) if > 5GB else 5GB
    """
    cache_size_form = lambda size: int(0.1 * mb_to_byte(size))
    cache_min_size = gb_to_byte(5)
    glance_mount_size = find_size_by_name(volumes, 'glance', 'image')
    cache_size = cache_size_form(glance_mount_size)
    return str(cache_size if cache_size > cache_min_size else cache_min_size)


def get_logical_volumes_by_name(volumes, name, id_type):
    for vg in only_vg(volumes):
        if vg.get('id') == id_type:
            for lv in vg['volumes']:
                if lv.get('name') == name:
                    yield lv


def find_size_by_name(volumes, name, id_type):
    """Find volumes with specific type
    """
    return sum(v.get('size', 0)
               for v in get_logical_volumes_by_name(volumes, name, id_type))


class DisksFormatConvertor(object):
    '''Class converts format from `simple` in which we
    communicate with UI to `full` in which we store
    data about disks\volumes in database, send to
    orchestrator and vice versa.

    Full disk format example:
        [
            {
                "type": "disk",
                "id": "sda",
                "size": 953869,
                "volumes": [
                    {
                        "mount": "/boot",
                        "type": "raid",
                        "size": 200
                    },
                    .....
                    {
                        "size": 938905,
                        "type": "pv",
                        "vg": "os"
                    }
                ]
            }
        ]

    Simple disk format example:
        [
            {
                "id": "sda",
                "size": 953869,
                "volumes": [
                    {
                        "name": "os",
                        "size": 938905,
                    }
                ]
            }
        ]
    '''

    @classmethod
    def format_disks_to_full(cls, node, disks):
        '''convert disks from simple format to full format
        '''
        full_format = []
        volume_manager = node.volume_manager
        for disk in disks:
            for volume in disk['volumes']:
                full_format = volume_manager.set_volume_size(
                    disk['id'], volume['name'], volume['size'])

        return full_format

    @classmethod
    def format_disks_to_simple(cls, full):
        '''convert disks from full format to simple format
        '''
        disks_in_simple_format = []

        # retrieve only physical disks
        disks_full_format = only_disks(full)

        for disk in disks_full_format:
            reserved_size = cls.calculate_service_partitions_size(
                disk['volumes'])

            lvm_pvs_size = sum([
                volume.get('lvm_meta_size', 0) for volume in disk['volumes']])
            size = 0
            if disk['size'] >= reserved_size:
                size = disk['size'] - reserved_size - lvm_pvs_size

            disk_simple = {
                'id': disk['id'],
                'name': disk['name'],
                'size': size,
                'volumes': cls.serialize_volumes(disk['volumes']),
                'extra': disk['extra'],
            }

            disks_in_simple_format.append(disk_simple)

        return disks_in_simple_format

    @classmethod
    def calculate_service_partitions_size(self, volumes):
        service_partitions = filter(is_service, volumes)
        return sum(
            [partition.get('size', 0) for partition in service_partitions])

    @classmethod
    def serialize_volumes(cls, all_partitions):
        """Convert volumes from full format to simple format
        """
        non_service_volumes = filter(
            lambda vg: not is_service(vg), all_partitions)

        pv_full_format = filter(
            lambda vg: vg.get('type') == 'pv', non_service_volumes)

        partitions_full_format = filter(
            lambda vg: vg.get('type') == 'partition', non_service_volumes)

        raid_full_format = filter(
            lambda vg: vg.get('type') == 'raid', non_service_volumes)

        volumes_simple_format = []
        for volume in pv_full_format:
            calculated_size = volume['size'] - volume['lvm_meta_size']
            size = calculated_size if calculated_size > 0 else 0

            volume_simple = {
                'name': volume['vg'],
                'size': size}

            volumes_simple_format.append(volume_simple)

        for partition in partitions_full_format:
            volumes_simple_format.append({
                'name': partition['name'],
                'size': partition['size']
            })

        for raid in raid_full_format:
            volumes_simple_format.append({
                'name': raid['name'],
                'size': raid['size']
            })

        return volumes_simple_format

    @classmethod
    def get_volumes_info(cls, node):
        '''Return volumes info for node

        :returns: [
                {
                    "name": "os",
                    "label": "Base System",
                    "minimum": 100002
                }
            ]
        '''
        volumes_info = []
        for space in get_node_spaces(node):
            # Here we calculate min_size of nodes
            min_size = node.volume_manager.expand_generators(
                space)['min_size']

            volumes_info.append({
                'name': space['id'],
                'label': space['label'],
                'min_size': min_size})

        return volumes_info


class Disk(object):

    def __init__(self, volumes, generator_method, disk_id, name,
                 size, boot_is_raid=True, possible_pvs_count=0,
                 disk_extra=None):
        """Create disk

        :param volumes: volumes which need to allocate on disk
        :param generator_method: method with size generator
        :param disk_id: uniq id for disk
        :param name: name, used for UI only
        :param size: size of disk
        :param boot_is_raid: if True partition_type
            equal to 'raid' else 'partition'
        :param possible_pvs_count: used for lvm pool calculation
            size of lvm pool = possible_pvs_count * lvm meta size
        """
        self.call_generator = generator_method
        self.id = disk_id
        self.extra = disk_extra or []
        self.name = name
        self.size = size
        self.lvm_meta_size = self.call_generator('calc_lvm_meta_size')
        self.max_lvm_meta_pool_size = self.lvm_meta_size * possible_pvs_count
        self.free_space = self.size
        self.set_volumes(volumes)

        # For determination type of boot
        self.boot_is_raid = boot_is_raid

        # For each disk we need to create
        # service partitions and reserve space
        self.create_service_partitions()

    def set_volumes(self, volumes):
        """Add volumes and reduce free space
        """
        self.volumes = volumes
        for volume in volumes:
            self.free_space -= volume.get('size', 0)

    def create_service_partitions(self):
        """Reserve space for service partitions
        """
        self.create_boot_records()
        self.create_boot_partition()
        self.create_lvm_meta_pool(self.max_lvm_meta_pool_size)

    def create_boot_partition(self):
        """Reserve space for boot partition
        """
        boot_size = self.call_generator('calc_boot_size')
        partition_type = 'partition'
        if self.boot_is_raid:
            partition_type = 'raid'

        existing_boot = filter(
            lambda volume: volume.get('mount') == '/boot', self.volumes)

        if not existing_boot:
            self.volumes.append({
                'type': partition_type,
                'file_system': 'ext2',
                'mount': '/boot',
                'name': 'Boot',
                'size': self.get_size(boot_size)})

    def create_boot_records(self):
        """Reserve space for efi, gpt, bios
        """
        boot_records_size = self.call_generator('calc_boot_records_size')
        existing_boot = filter(
            lambda volume: volume.get('type') == 'boot', self.volumes)

        if not existing_boot:
            self.volumes.append(
                {'type': 'boot', 'size': self.get_size(boot_records_size)})

    def get_size(self, size):
        """Get size and reduce free space. Returns 0 if
        not enough free space.
        """
        size_to_allocate = size if self.free_space >= size else 0
        self.free_space -= size_to_allocate
        return size_to_allocate

    def create_lvm_meta_pool(self, size):
        """Create lvm pool.
        When new PV will be created, from this pool
        deducated size of single lvm meta for each
        PV on disk.
        """
        existing_lvm_pool = filter(
            lambda volume: volume['type'] == 'lvm_meta_pool', self.volumes)

        if not existing_lvm_pool:
            self.volumes.append(
                {'type': 'lvm_meta_pool', 'size': self.get_size(size)})

    def get_lvm_meta_from_pool(self):
        """Take lvm meta from lvm meta pool
        """
        lvm_meta_pool = filter(
            lambda volume: volume['type'] == 'lvm_meta_pool', self.volumes)[0]

        if lvm_meta_pool['size'] >= self.lvm_meta_size:
            lvm_meta_pool['size'] -= self.lvm_meta_size
            allocated_size = self.lvm_meta_size
        else:
            allocated_size = 0

        return allocated_size

    def put_size_to_lvm_meta_pool(self, size):
        """Return back lvm meta to pool
        """
        lvm_meta_pool = filter(
            lambda volume: volume['type'] == 'lvm_meta_pool', self.volumes)[0]

        lvm_meta_pool['size'] += size

    def create_pv(self, volume_info, size=None):
        """Allocates all available space if size is None
        Size in parameter should include size of lvm meta
        """
        name = volume_info['id']
        logger.debug('Creating PV: disk=%s vg=%s, size=%s',
                     self.id, name, str(size))

        if size is None:
            logger.debug(
                'Size is not defined. Will use all free space on this disk.')
            size = self.free_space

        self.free_space -= size
        # Don't allocate lvm if size equal 0
        lvm_meta_size = self.get_lvm_meta_from_pool() if size else 0

        logger.debug('Appending PV to volumes.')
        self.volumes.append({
            'type': 'pv',
            'vg': name,
            'size': size + lvm_meta_size,
            'lvm_meta_size': lvm_meta_size})

    def create_partition(self, partition_info, size=None, ptype='partition'):
        """Create partitions according templates in partition_info
        """
        logger.debug('Creating or updating partition: disk=%s patition=%s',
                     self.id, partition_info)

        if size is None:
            logger.debug(
                'Size is not defined. Will use all free space on this disk.')
            size = self.free_space

        self.free_space -= size

        self.volumes.append({
            'size': size,
            'type': ptype,
            'name': partition_info['id'],
            'file_system': partition_info['file_system'],
            'disk_label': partition_info.get('disk_label'),
            'partition_guid': partition_info.get('partition_guid'),
            'mount': partition_info['mount']})

    def remove_pv(self, name):
        """Remove PV and return back lvm_meta size to pool
        """
        for i, volume in enumerate(self.volumes[:]):
            if volume.get('type') == 'pv' and volume.get('vg') == name:
                lvm_meta_pool = filter(
                    lambda v: v['type'] == 'lvm_meta_pool', self.volumes)[0]

                # Return back size to lvm_meta_pool
                lvm_meta_pool['size'] += volume['lvm_meta_size']
                # Return back size of PV, without size of lvm meta
                # beacuse we return back size of lvm_meta above
                self.free_space += (volume['size'] - volume['lvm_meta_size'])

                del self.volumes[i]
                break

    def set_pv_size(self, name, size):
        """Set PV size
        """
        for volume in self.volumes:
            if volume.get('type') == 'pv' and volume.get('vg') == name:
                # Recreate lvm meta
                self.remove_pv(name)
                self.create_pv({"id": name}, size)

    def set_partition_size(self, name, size):
        """Set partition size
        """
        for volume in self.volumes:
            if volume.get('type') == 'partition' and \
               volume.get('name') == name:
                self.free_space += volume['size']
                volume['size'] = size
                self.free_space -= size

    def set_raid_size(self, name, size):
        """Set partition size
        """
        for volume in self.volumes:
            if volume.get('type') == 'raid' and \
               volume.get('name') == name and \
               volume.get('mount') != '/boot':
                self.free_space += volume['size']
                volume['size'] = size
                self.free_space -= size

    def reset(self):
        self.volumes = []
        self.free_space = self.size
        self.create_service_partitions()

    def render(self):
        return {
            'id': self.id,
            'extra': self.extra,
            'name': self.name,
            'type': 'disk',
            'size': self.size,
            'volumes': self.volumes,
            'free_space': self.free_space
        }

    def __repr__(self):
        return jsonutils.dumps(self.render())

    def __str__(self):
        return jsonutils.dumps(self.render(), indent=4)


class VolumeManager(object):
    def __init__(self, node):
        """Disks and volumes will be set according to node attributes.
        VolumeManager should not make any updates in database.
        """
        self.node_name = node.name

        # Make sure that we don't change volumes directly from manager
        self.volumes = deepcopy(node.attributes.volumes) or []
        # For swap calculation
        self.ram = node.meta['memory']['total']
        self.allowed_volumes = []

        # If node bound to the cluster than it has a role
        # and volume groups which we should to allocate
        if node.cluster:
            self.allowed_volumes = get_node_spaces(node)

        self.disks = []
        for d in sorted(node.meta['disks'], key=lambda i: i['name']):
            disks_count = len(node.meta["disks"])
            boot_is_raid = True if disks_count > 1 else False

            existing_disk = filter(
                lambda disk: d['disk'] == disk['id'],
                only_disks(self.volumes))

            disk_volumes = existing_disk[0].get(
                'volumes', []) if existing_disk else []

            disk = Disk(
                disk_volumes,
                self.call_generator,
                d["disk"],
                d["name"],
                byte_to_megabyte(d["size"]),
                boot_is_raid=boot_is_raid,
                # Count of possible PVs equal to count of allowed VGs
                possible_pvs_count=len(only_vg(self.allowed_volumes)),
                disk_extra=d.get("extra", []))

            self.disks.append(disk)

        self.__logger('Initialized with node: %s' % node.full_name)
        self.__logger('Initialized with volumes: %s' % self.volumes)
        self.__logger('Initialized with disks: %s' % self.disks)

    def set_volume_size(self, disk_id, volume_name, size):
        """Set size of volume
        """
        self.__logger('Update volume size for disk=%s volume_name=%s size=%s' %
                      (disk_id, volume_name, size))

        disk = filter(lambda disk: disk.id == disk_id, self.disks)[0]

        volume_type = self.get_space_type(volume_name)
        if volume_type == 'partition':
            disk.set_partition_size(volume_name, size)
        elif volume_type == 'vg':
            disk.set_pv_size(volume_name, size)
        elif volume_type == 'raid':
            disk.set_raid_size(volume_name, size)

        for idx, volume in enumerate(self.volumes):
            if volume.get('id') == disk.id:
                self.volumes[idx] = disk.render()

        # Recalculate sizes of volume groups
        for idx, volume in enumerate(self.volumes):
            if volume.get('type') == 'vg':
                vg_id = volume.get('id')
                vg_template = filter(
                    lambda volume: volume.get('id') == vg_id,
                    self.allowed_volumes)[0]

                self.volumes[idx] = self.expand_generators(vg_template)

        self.__logger('Updated volume size %s' % self.volumes)
        return self.volumes

    def get_space_type(self, volume_name):
        """Get type of space which represents on disk
        as volume with volume_name
        """
        for volume in self.allowed_volumes:
            if volume['id'] == volume_name:
                return volume['type']

    def get_pv_size(self, disk_id, volume_name):
        """Get PV size without lvm meta size
        """
        disk = filter(
            lambda volume: volume['id'] == disk_id,
            only_disks(self.volumes))[0]

        volume = filter(
            lambda volume: volume_name == volume.get('vg'),
            disk['volumes'])[0]

        size_without_lvm_meta = volume['size'] - \
            self.call_generator('calc_lvm_meta_size')

        return size_without_lvm_meta

    def get_total_allocated_size(self, name):
        size = 0
        for disk in self.disks:
            for volume in disk.volumes:
                if volume.get('name') == name or volume.get('vg') == name:
                    size += volume['size']

        return size

    def call_generator(self, generator, *args):
        generators = {
            # Calculate swap space based on total RAM
            'calc_swap_size': self._calc_swap_size,
            # 15G <= root <= 50G
            'calc_root_size': self._calc_root_size,
            # boot = 200MB
            'calc_boot_size': lambda: 200,
            # boot records size = 300MB
            'calc_boot_records_size': lambda: 300,
            # let's think that size of mbr is 10MB
            'calc_mbr_size': lambda: 10,
            # lvm meta = 64MB for one volume group
            'calc_lvm_meta_size': lambda: 64,
            'calc_total_vg': self._calc_total_vg,
            # virtual storage = 5GB
            'calc_min_vm_size': lambda: gb_to_mb(5),
            'calc_min_glance_size': lambda: gb_to_mb(5),
            'calc_min_cinder_size': lambda: gb_to_mb(1.5),
            'calc_min_mongo_size': lambda: gb_to_mb(10),
            'calc_total_root_vg': self._calc_total_root_vg,
            # 2GB reuquired for journal, leave 1GB for data
            'calc_min_ceph_size': lambda: gb_to_mb(3),
            'calc_min_ceph_journal_size': lambda: 0,
            'calc_min_mysql_size': lambda: gb_to_mb(10)
        }

        generators['calc_os_size'] = \
            lambda: generators['calc_root_size']() + \
            generators['calc_swap_size']()

        generators['calc_os_vg_size'] = generators['calc_os_size']
        generators['calc_min_os_size'] = generators['calc_os_size']

        if generator not in generators:
            raise errors.CannotFindGenerator(
                u'Cannot find generator %s' % generator)

        result = generators[generator](*args)
        self.__logger('Generator %s with args %s returned result: %s' %
                      (generator, args, result))
        return result

    def _calc_root_size(self):
        size = int(self.disks[0].size * 0.2)
        if size < gb_to_mb(15):
            size = gb_to_mb(15)
        elif size > gb_to_mb(50):
            size = gb_to_mb(50)
        return size

    def _calc_total_root_vg(self):
        return self._calc_total_vg('os') - \
            self.call_generator('calc_swap_size')

    def _calc_total_vg(self, vg):
        vg_space = 0
        for v in only_disks(self.volumes):
            for subv in v['volumes']:
                if subv.get('type') == 'pv' and subv.get('vg') == vg:
                    vg_space += subv.get('size', 0) - \
                        subv.get('lvm_meta_size', 0)

        return vg_space

    def _calc_swap_size(self):
        '''Calc swap size according to RAM

        | RAM          | Recommended swap space      |
        |--------------+-----------------------------|
        | <= 2GB       | 2 times the amount of RAM   |
        | > 2GB – 8GB  | Equal to the amount of RAM  |
        | > 8GB – 64GB | 0.5 times the amount of RAM |
        | > 64GB       | 4GB of swap space           |

        Source https://access.redhat.com/site/documentation/en-US/
                       Red_Hat_Enterprise_Linux/6/html/Installation_Guide/
                       s2-diskpartrecommend-ppc.html#id4394007
        '''
        mem = int(float(self.ram) / 1024 ** 2)
        if mem <= 2048:
            return (2 * mem)
        elif mem > 2048 and mem <= 8192:
            return mem
        elif mem > 8192 and mem <= 65536:
            return int(.5 * mem)
        else:
            return gb_to_mb(4)

    def _allocate_all_free_space_for_volume(self, volume_info):
        """Allocate all existing space on all disks."""
        self.__logger('Allocate all free space for volume %s ' % (volume_info))

        for disk in self.disks:
            if disk.free_space > 0:
                self.__logger('Allocating all available space for volume: '
                              'disk: %s volume: %s' %
                              (disk.id, volume_info))
                self._get_allocator(disk, volume_info)(volume_info)
            else:
                self.__logger('Not enough free space for volume '
                              'allocation: disk: %s volume: %s' %
                              (disk.id, volume_info))
                self._get_allocator(disk, volume_info)(volume_info, 0)

    def _allocate_size_for_volume(self, volume_info, size):
        """Allocate volumes with particaular size."""
        self.__logger('Allocate volume %s with size %s ' % (volume_info, size))

        not_allocated_size = size
        for disk in self.disks:
            self.__logger('Creating volume: disk: %s, vg: %s' %
                          (disk.id, volume_info))

            if disk.free_space >= not_allocated_size:
                # if we can allocate all required size
                # on one disk, then just allocate it
                size_to_allocation = not_allocated_size
            elif disk.free_space > 0:
                # if disk has free space, then allocate it
                size_to_allocation = disk.free_space
            else:
                # else just allocate volume with size 0
                size_to_allocation = 0

            self._get_allocator(disk, volume_info)(volume_info,
                                                   size_to_allocation)
            not_allocated_size -= size_to_allocation

    def _allocate_full_disk(self, volume_info):
        """Allocate full disks for a volume."""
        self.__logger('Allocate full disk for volume %s ' % (volume_info))

        for disk in self.disks:
            existing_volumes = [v for v in disk.volumes if not is_service(v)
                                and v['size'] > 0]
            if len(existing_volumes) > 0:
                self._get_allocator(disk, volume_info)(volume_info, 0)
            else:
                self._get_allocator(disk, volume_info)(volume_info)

    def _get_allocator(self, disk, volume_info):
        """Returns disk method for volume allocation
        """
        if volume_info['type'] == 'vg':
            return disk.create_pv
        elif volume_info['type'] == 'partition':
            return disk.create_partition
        elif volume_info['type'] == 'raid':
            return partial(disk.create_partition, ptype='raid')

    def gen_volumes_info(self):
        self.__logger('Generating volumes info for node')
        self.__logger('Purging volumes info for all node disks')

        map(lambda d: d.reset(), self.disks)
        self.volumes = [d.render() for d in self.disks]

        if not self.allowed_volumes:
            self.__logger('Role is None return volumes: %s' % self.volumes)
            return self.volumes

        self.volumes.extend(only_vg(self.allowed_volumes))

        # Firstly allocate volumes which required
        # minimal size

        for volume in self._min_size_volumes:
            min_size = self.expand_generators(volume)['min_size']
            self._allocate_size_for_volume(volume, min_size)

        # Allocate volumes which prefer an entire disk
        for volume in self._full_disk_volumes:
            self._allocate_full_disk(volume)

        # Then allocate volumes which required
        # all free space
        if len(self._all_size_volumes) > 1:
            size = self._all_disks_free_space / len(self._all_size_volumes)
            for volume in self._all_size_volumes[:-1]:
                self._allocate_size_for_volume(volume, size)

        # And allocate rest of the space for
        # last volume. We want to be sure
        # that we use all free space.
        # Problem which we solve with such approach:
        # we can loose 1 mb in calculation above
        if self._all_size_volumes:
            self._allocate_all_free_space_for_volume(
                self._all_size_volumes[-1])

        self.volumes = self.expand_generators(self.volumes)

        self.__logger('Generated volumes: %s' % self.volumes)
        return self.volumes

    @property
    def _all_disks_free_space(self):
        return sum([d.free_space for d in self.disks])

    @property
    def _min_size_volumes(self):
        return filter(
            lambda volume: volume['_allocate_size'] == 'min',
            self.allowed_volumes)

    @property
    def _all_size_volumes(self):
        return filter(
            lambda volume: volume['_allocate_size'] == 'all',
            self.allowed_volumes)

    @property
    def _full_disk_volumes(self):
        return filter(
            lambda volume: volume['_allocate_size'] == 'full-disk',
            self.allowed_volumes)

    def expand_generators(self, value):
        if isinstance(value, (str, unicode, int, float, long)):
            return value
        elif isinstance(value, dict):
            generator = value.get("generator")
            generator_args = value.get("generator_args", [])
            if generator is not None:
                genval = self.call_generator(
                    generator, *generator_args)
                self.__logger(
                    'Generator {0} with args {1} expanded to: {2}'.format(
                        generator, generator_args, genval))
                return genval
            else:
                return dict((k, self.expand_generators(v))
                            for (k, v) in value.iteritems())
        elif isinstance(value, list):
            return [self.expand_generators(i) for i in value]
        return value

    def check_disk_space_for_deployment(self):
        '''Check disks space for minimal installation.
        This method calls in before deployment task.

        :raises: errors.NotEnoughFreeSpace
        '''
        disks_space = sum([d.size for d in self.disks])
        minimal_installation_size = self.__calc_minimal_installation_size()

        self.__logger(
            'Checking disks space: disks space {0}, minimal size {1}'.format(
                disks_space,
                minimal_installation_size
            )
        )

        if disks_space < minimal_installation_size:
            raise errors.NotEnoughFreeSpace()

    def check_volume_sizes_for_deployment(self):
        vg_errors = []

        for volume in self.allowed_volumes:
            vg_size = self.get_total_allocated_size(volume['id'])
            min_size = self.expand_generators(volume)['min_size']
            if vg_size < min_size:
                vg_errors.append([volume['label'], min_size])

        if vg_errors:
            msgs = ["Volume group '{0}' requires a minimum of {1}MB".format(*v)
                    for v in vg_errors]
            raise errors.NotEnoughFreeSpace('\n'.join(msgs))

    def __calc_minimal_installation_size(self):
        '''Calc minimal installation size depend on node role
        '''
        disks_count = len(filter(lambda disk: disk.size > 0, self.disks))
        boot_size = self.call_generator('calc_boot_size') + \
            self.call_generator('calc_boot_records_size')

        min_installation_size = disks_count * boot_size
        for volume in self.allowed_volumes:
            min_size = self.expand_generators(volume)['min_size']
            min_installation_size += min_size

        return min_installation_size

    def __logger(self, message):
        logger.debug('VolumeManager %s: %s', id(self), message)
