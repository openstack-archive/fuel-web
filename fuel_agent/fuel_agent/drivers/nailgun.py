# Copyright 2014 Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import itertools
import math
import os
import six
import yaml

from six.moves.urllib.parse import urljoin
from six.moves.urllib.parse import urlparse
from six.moves.urllib.parse import urlsplit

from fuel_agent.drivers.base import BaseDataDriver
from fuel_agent.drivers import ks_spaces_validator
from fuel_agent import errors
from fuel_agent import objects
from fuel_agent.openstack.common import log as logging
from fuel_agent.utils import hardware as hu
from fuel_agent.utils import utils


LOG = logging.getLogger(__name__)


def match_device(hu_disk, ks_disk):
    """Check if hu_disk and ks_disk are the same device

    Tries to figure out if hu_disk got from hu.list_block_devices
    and ks_spaces_disk given correspond to the same disk device. This
    is the simplified version of hu.match_device

    :param hu_disk: A dict representing disk device how
    it is given by list_block_devices method.
    :param ks_disk: A dict representing disk device according to
     ks_spaces format.

    :returns: True if hu_disk matches ks_spaces_disk else False.
    """
    uspec = hu_disk['uspec']

    # True if at least one by-id link matches ks_disk
    if ('DEVLINKS' in uspec and len(ks_disk.get('extra', [])) > 0
            and any(x.startswith('/dev/disk/by-id') for x in
                    set(uspec['DEVLINKS']) &
                    set(['/dev/%s' % l for l in ks_disk['extra']]))):
        return True

    # True if one of DEVLINKS matches ks_disk id
    if (len(ks_disk.get('extra', [])) == 0
            and 'DEVLINKS' in uspec and 'id' in ks_disk
            and '/dev/%s' % ks_disk['id'] in uspec['DEVLINKS']):
        return True

    return False


class Nailgun(BaseDataDriver):
    def __init__(self, data):
        super(Nailgun, self).__init__(data)

        # this var states whether boot partition
        # was already allocated on first matching volume
        # or not
        self._boot_partition_done = False
        # this var is used as a flag that /boot fs
        # has already been added. we need this to
        # get rid of md over all disks for /boot partition.
        self._boot_done = False

        self.partition_scheme = self.parse_partition_scheme()
        self.grub = self.parse_grub()
        self.configdrive_scheme = self.parse_configdrive_scheme()
        # parsing image scheme needs partition scheme has been parsed
        self.image_scheme = self.parse_image_scheme()

    def partition_data(self):
        return self.data['ks_meta']['pm_data']['ks_spaces']

    @property
    def ks_disks(self):
        return filter(
            lambda x: x['type'] == 'disk' and x['size'] > 0,
            self.partition_data())

    @property
    def small_ks_disks(self):
        """Get those disks which are smaller than 2T"""
        return [d for d in self.ks_disks if d['size'] <= 2097152]

    @property
    def ks_vgs(self):
        return filter(
            lambda x: x['type'] == 'vg',
            self.partition_data())

    @property
    def hu_disks(self):
        """Actual disks which are available on this node

        It is a list of dicts which are formatted other way than
        ks_spaces disks. To match both of those formats use
        _match_device method.
        """
        if not getattr(self, '_hu_disks', None):
            self._hu_disks = hu.list_block_devices(disks=True)
        return self._hu_disks

    def _disk_dev(self, ks_disk):
        # first we try to find a device that matches ks_disk
        # comparing by-id and by-path links
        matched = [hu_disk['device'] for hu_disk in self.hu_disks
                   if match_device(hu_disk, ks_disk)]
        # if we can not find a device by its by-id and by-path links
        # we try to find a device by its name
        fallback = [hu_disk['device'] for hu_disk in self.hu_disks
                    if '/dev/%s' % ks_disk['name'] == hu_disk['device']]
        found = matched or fallback
        if not found or len(found) > 1:
            raise errors.DiskNotFoundError(
                'Disk not found: %s' % ks_disk['name'])
        return found[0]

    def _getlabel(self, label):
        if not label:
            return ''
        # XFS will refuse to format a partition if the
        # disk label is > 12 characters.
        return ' -L {0} '.format(label[:12])

    def _get_partition_count(self, name):
        count = 0
        for disk in self.ks_disks:
            count += len([v for v in disk["volumes"]
                          if v.get('name') == name and v['size'] > 0])
        return count

    def _num_ceph_journals(self):
        return self._get_partition_count('cephjournal')

    def _num_ceph_osds(self):
        return self._get_partition_count('ceph')

    def parse_partition_scheme(self):
        LOG.debug('--- Preparing partition scheme ---')
        data = self.partition_data()
        ks_spaces_validator.validate(data)
        partition_scheme = objects.PartitionScheme()

        ceph_osds = self._num_ceph_osds()
        journals_left = ceph_osds
        ceph_journals = self._num_ceph_journals()

        LOG.debug('Looping over all disks in provision data')
        for disk in self.ks_disks:
            # skipping disk if there are no volumes with size >0
            # to be allocated on it which are not boot partitions
            if all((
                v["size"] <= 0
                for v in disk["volumes"]
                if v["type"] != "boot" and v.get("mount") != "/boot"
            )):
                continue
            LOG.debug('Processing disk %s' % disk['name'])
            LOG.debug('Adding gpt table on disk %s' % disk['name'])
            parted = partition_scheme.add_parted(
                name=self._disk_dev(disk), label='gpt')
            # we install bootloader on every disk
            LOG.debug('Adding bootloader stage0 on disk %s' % disk['name'])
            parted.install_bootloader = True
            # legacy boot partition
            LOG.debug('Adding bios_grub partition on disk %s: size=24' %
                      disk['name'])
            parted.add_partition(size=24, flags=['bios_grub'])
            # uefi partition (for future use)
            LOG.debug('Adding UEFI partition on disk %s: size=200' %
                      disk['name'])
            parted.add_partition(size=200)

            LOG.debug('Looping over all volumes on disk %s' % disk['name'])
            for volume in disk['volumes']:
                LOG.debug('Processing volume: '
                          'name=%s type=%s size=%s mount=%s vg=%s' %
                          (volume.get('name'), volume.get('type'),
                           volume.get('size'), volume.get('mount'),
                           volume.get('vg')))
                if volume['size'] <= 0:
                    LOG.debug('Volume size is zero. Skipping.')
                    continue

                if volume.get('name') == 'cephjournal':
                    LOG.debug('Volume seems to be a CEPH journal volume. '
                              'Special procedure is supposed to be applied.')
                    # We need to allocate a journal partition for each ceph OSD
                    # Determine the number of journal partitions we need on
                    # each device
                    ratio = int(math.ceil(float(ceph_osds) / ceph_journals))

                    # No more than 10GB will be allocated to a single journal
                    # partition
                    size = volume["size"] / ratio
                    if size > 10240:
                        size = 10240

                    # This will attempt to evenly spread partitions across
                    # multiple devices e.g. 5 osds with 2 journal devices will
                    # create 3 partitions on the first device and 2 on the
                    # second
                    if ratio < journals_left:
                        end = ratio
                    else:
                        end = journals_left

                    for i in range(0, end):
                        journals_left -= 1
                        if volume['type'] == 'partition':
                            LOG.debug('Adding CEPH journal partition on '
                                      'disk %s: size=%s' %
                                      (disk['name'], size))
                            prt = parted.add_partition(size=size)
                            LOG.debug('Partition name: %s' % prt.name)
                            if 'partition_guid' in volume:
                                LOG.debug('Setting partition GUID: %s' %
                                          volume['partition_guid'])
                                prt.set_guid(volume['partition_guid'])
                    continue

                if volume['type'] in ('partition', 'pv', 'raid'):
                    if volume.get('mount') != '/boot':
                        LOG.debug('Adding partition on disk %s: size=%s' %
                                  (disk['name'], volume['size']))
                        prt = parted.add_partition(
                            size=volume['size'],
                            keep=volume.get('keep', False))
                        LOG.debug('Partition name: %s' % prt.name)

                    elif volume.get('mount') == '/boot' \
                            and not self._boot_partition_done \
                            and (disk in self.small_ks_disks or
                                 not self.small_ks_disks):
                        # NOTE(kozhukalov): On some hardware GRUB is not able
                        # to see disks larger than 2T due to firmware bugs,
                        # so we'd better avoid placing /boot on such
                        # huge disks if it is possible.
                        LOG.debug('Adding /boot partition on disk %s: '
                                  'size=%s', disk['name'], volume['size'])
                        prt = parted.add_partition(
                            size=volume['size'],
                            keep=volume.get('keep', False))
                        LOG.debug('Partition name: %s', prt.name)
                        self._boot_partition_done = True
                    else:
                        LOG.debug('No need to create partition on disk %s. '
                                  'Skipping.', disk['name'])
                        continue

                if volume['type'] == 'partition':
                    if 'partition_guid' in volume:
                        LOG.debug('Setting partition GUID: %s' %
                                  volume['partition_guid'])
                        prt.set_guid(volume['partition_guid'])

                    if 'mount' in volume and volume['mount'] != 'none':
                        LOG.debug('Adding file system on partition: '
                                  'mount=%s type=%s' %
                                  (volume['mount'],
                                   volume.get('file_system', 'xfs')))
                        partition_scheme.add_fs(
                            device=prt.name, mount=volume['mount'],
                            fs_type=volume.get('file_system', 'xfs'),
                            fs_label=self._getlabel(volume.get('disk_label')))
                        if volume['mount'] == '/boot' and not self._boot_done:
                            self._boot_done = True

                if volume['type'] == 'pv':
                    LOG.debug('Creating pv on partition: pv=%s vg=%s' %
                              (prt.name, volume['vg']))
                    lvm_meta_size = volume.get('lvm_meta_size', 64)
                    # The reason for that is to make sure that
                    # there will be enough space for creating logical volumes.
                    # Default lvm extension size is 4M. Nailgun volume
                    # manager does not care of it and if physical volume size
                    # is 4M * N + 3M and lvm metadata size is 4M * L then only
                    # 4M * (N-L) + 3M of space will be available for
                    # creating logical extensions. So only 4M * (N-L) of space
                    # will be available for logical volumes, while nailgun
                    # volume manager might reguire 4M * (N-L) + 3M
                    # logical volume. Besides, parted aligns partitions
                    # according to its own algorithm and actual partition might
                    # be a bit smaller than integer number of mebibytes.
                    if lvm_meta_size < 10:
                        raise errors.WrongPartitionSchemeError(
                            'Error while creating physical volume: '
                            'lvm metadata size is too small')
                    metadatasize = int(math.floor((lvm_meta_size - 8) / 2))
                    metadatacopies = 2
                    partition_scheme.vg_attach_by_name(
                        pvname=prt.name, vgname=volume['vg'],
                        metadatasize=metadatasize,
                        metadatacopies=metadatacopies)

                if volume['type'] == 'raid':
                    if 'mount' in volume and \
                            volume['mount'] not in ('none', '/boot'):
                        LOG.debug('Attaching partition to RAID '
                                  'by its mount point %s' % volume['mount'])
                        partition_scheme.md_attach_by_mount(
                            device=prt.name, mount=volume['mount'],
                            fs_type=volume.get('file_system', 'xfs'),
                            fs_label=self._getlabel(volume.get('disk_label')))

                    if 'mount' in volume and volume['mount'] == '/boot' and \
                            not self._boot_done:
                        LOG.debug('Adding file system on partition: '
                                  'mount=%s type=%s' %
                                  (volume['mount'],
                                   volume.get('file_system', 'ext2')))
                        partition_scheme.add_fs(
                            device=prt.name, mount=volume['mount'],
                            fs_type=volume.get('file_system', 'ext2'),
                            fs_label=self._getlabel(volume.get('disk_label')))
                        self._boot_done = True

            # this partition will be used to put there configdrive image
            if partition_scheme.configdrive_device() is None:
                LOG.debug('Adding configdrive partition on disk %s: size=20' %
                          disk['name'])
                parted.add_partition(size=20, configdrive=True)

        # checking if /boot is created
        if not self._boot_partition_done or not self._boot_done:
            raise errors.WrongPartitionSchemeError(
                '/boot partition has not been created for some reasons')

        LOG.debug('Looping over all volume groups in provision data')
        for vg in self.ks_vgs:
            LOG.debug('Processing vg %s' % vg['id'])
            LOG.debug('Looping over all logical volumes in vg %s' % vg['id'])
            for volume in vg['volumes']:
                LOG.debug('Processing lv %s' % volume['name'])
                if volume['size'] <= 0:
                    LOG.debug('Lv size is zero. Skipping.')
                    continue

                if volume['type'] == 'lv':
                    LOG.debug('Adding lv to vg %s: name=%s, size=%s' %
                              (vg['id'], volume['name'], volume['size']))
                    lv = partition_scheme.add_lv(name=volume['name'],
                                                 vgname=vg['id'],
                                                 size=volume['size'])

                    if 'mount' in volume and volume['mount'] != 'none':
                        LOG.debug('Adding file system on lv: '
                                  'mount=%s type=%s' %
                                  (volume['mount'],
                                   volume.get('file_system', 'xfs')))
                        partition_scheme.add_fs(
                            device=lv.device_name, mount=volume['mount'],
                            fs_type=volume.get('file_system', 'xfs'),
                            fs_label=self._getlabel(volume.get('disk_label')))

        partition_scheme = self.carry_keep_flags(partition_scheme)

        return partition_scheme

    def carry_keep_flags(self, partition_scheme):
        LOG.debug('Carry keep flags')

        for vg in partition_scheme.vgs:
            for pvname in vg.pvnames:
                partition = partition_scheme.partition_by_name(pvname)
                if partition and partition.keep:
                    partition.keep = False
                    LOG.debug('Set keep flag to vg=%s' % vg.name)
                    vg.set_vg_keep(True)

        for lv in partition_scheme.lvs:
            vg = partition_scheme.vg_by_name(lv.vgname)
            if vg.vg_keep:
                lv.set_lv_keep(True)

        # Need loop over lv again to remove keep flag from vg
        for lv in partition_scheme.lvs:
            vg = partition_scheme.vg_by_name(lv.vgname)
            if vg.vg_keep and lv.lv_keep:
                vg.set_vg_keep(False)

        for fs in partition_scheme.fss:
            lv = partition_scheme.lv_by_device_name(fs.device)
            if lv:
                if lv.lv_keep:
                    LOG.debug('Set keep flag to fs=%s from lv=%s' %
                              (fs.mount, lv.name))
                    lv.set_lv_keep(False)
                    fs.set_fs_keep(True)
                continue
            partition = partition_scheme.partition_by_name(fs.device)
            if partition and 'keep' in partition.flags:
                LOG.debug('Set keep flag to fs=%s from partition=%s' %
                          (fs.mount, partition.name))
                partition.keep = False
                fs.set_fs_flag(True)

        return partition_scheme

    def parse_configdrive_scheme(self):
        LOG.debug('--- Preparing configdrive scheme ---')
        data = self.data
        configdrive_scheme = objects.ConfigDriveScheme()

        LOG.debug('Adding common parameters')
        admin_interface = filter(
            lambda x: (x['mac_address'] ==
                       data['kernel_options']['netcfg/choose_interface']),
            [dict(name=name, **spec) for name, spec
             in data['interfaces'].iteritems()])[0]

        ssh_auth_keys = data['ks_meta']['authorized_keys']
        if data['ks_meta']['auth_key']:
            ssh_auth_keys.append(data['ks_meta']['auth_key'])

        configdrive_scheme.set_common(
            ssh_auth_keys=ssh_auth_keys,
            hostname=data['hostname'],
            fqdn=data['hostname'],
            name_servers=data['name_servers'],
            search_domain=data['name_servers_search'],
            master_ip=data['ks_meta']['master_ip'],
            master_url='http://%s:8000/api' % data['ks_meta']['master_ip'],
            udevrules=data['kernel_options']['udevrules'],
            admin_mac=data['kernel_options']['netcfg/choose_interface'],
            admin_ip=admin_interface['ip_address'],
            admin_mask=admin_interface['netmask'],
            admin_iface_name=admin_interface['name'],
            timezone=data['ks_meta'].get('timezone', 'America/Los_Angeles'),
            gw=data['ks_meta']['gw'],
            ks_repos=data['ks_meta']['repo_setup']['repos']
        )

        LOG.debug('Adding puppet parameters')
        configdrive_scheme.set_puppet(
            master=data['ks_meta']['puppet_master'],
            enable=data['ks_meta']['puppet_enable']
        )

        LOG.debug('Adding mcollective parameters')
        configdrive_scheme.set_mcollective(
            pskey=data['ks_meta']['mco_pskey'],
            vhost=data['ks_meta']['mco_vhost'],
            host=data['ks_meta']['mco_host'],
            user=data['ks_meta']['mco_user'],
            password=data['ks_meta']['mco_password'],
            connector=data['ks_meta']['mco_connector'],
            enable=data['ks_meta']['mco_enable']
        )

        LOG.debug('Setting configdrive profile %s' % data['profile'])
        configdrive_scheme.set_profile(profile=data['profile'])
        return configdrive_scheme

    def parse_grub(self):
        LOG.debug('--- Parse grub settings ---')
        grub = objects.Grub()
        LOG.debug('Appending kernel parameters: %s',
                  self.data['ks_meta']['pm_data']['kernel_params'])
        grub.append_kernel_params(
            self.data['ks_meta']['pm_data']['kernel_params'])
        if 'centos' in self.data['profile'].lower() and \
                not self.data['ks_meta'].get('kernel_lt'):
            LOG.debug('Prefered kernel version is 2.6')
            grub.kernel_regexp = r'^vmlinuz-2\.6.*'
            grub.initrd_regexp = r'^initramfs-2\.6.*'
        return grub

    def parse_image_scheme(self):
        LOG.debug('--- Preparing image scheme ---')
        data = self.data
        image_scheme = objects.ImageScheme()
        # FIXME(agordeev): this piece of code for fetching additional image
        # meta data should be factored out of this particular nailgun driver
        # into more common and absract data getter which should be able to deal
        # with various data sources (local file, http(s), etc.) and different
        # data formats ('blob', json, yaml, etc.).
        # So, the manager will combine and manipulate all those multiple data
        # getter instances.
        # Also, the initial data source should be set to sort out chicken/egg
        # problem. Command line option may be useful for such a case.
        # BUG: https://bugs.launchpad.net/fuel/+bug/1430418
        root_uri = data['ks_meta']['image_data']['/']['uri']
        filename = os.path.basename(urlparse(root_uri).path).split('.')[0] + \
            '.yaml'
        metadata_url = urljoin(root_uri, filename)
        try:
            image_meta = yaml.load(
                utils.init_http_request(metadata_url).text)
        except Exception as e:
            LOG.exception(e)
            LOG.debug('Failed to fetch/decode image meta data')
            image_meta = {}
        # We assume for every file system user may provide a separate
        # file system image. For example if partitioning scheme has
        # /, /boot, /var/lib file systems then we will try to get images
        # for all those mount points. Images data are to be defined
        # at provision.json -> ['ks_meta']['image_data']
        LOG.debug('Looping over all images in provision data')
        for mount_point, image_data in six.iteritems(
                data['ks_meta']['image_data']):
            LOG.debug('Adding image for fs %s: uri=%s format=%s container=%s' %
                      (mount_point, image_data['uri'],
                       image_data['format'], image_data['container']))
            iname = os.path.basename(urlparse(image_data['uri']).path)
            imeta = next(itertools.chain(
                (img for img in image_meta.get('images', [])
                 if img['container_name'] == iname), [{}]))
            image_scheme.add_image(
                uri=image_data['uri'],
                target_device=self.partition_scheme.fs_by_mount(
                    mount_point).device,
                format=image_data['format'],
                container=image_data['container'],
                size=imeta.get('raw_size'),
                md5=imeta.get('raw_md5'),
            )
        return image_scheme


class NailgunBuildImage(BaseDataDriver):

    # TODO(kozhukalov):
    # This list of packages is used by default only if another
    # list isn't given in build image data. In the future
    # we need to handle package list in nailgun. Even more,
    # in the future, we'll be building not only ubuntu images
    # and we'll likely move this list into some kind of config.
    DEFAULT_TRUSTY_PACKAGES = [
        "acl",
        "anacron",
        "bash-completion",
        "bridge-utils",
        "bsdmainutils",
        "build-essential",
        "cloud-init",
        "curl",
        "daemonize",
        "debconf-utils",
        "gdisk",
        "grub-pc",
        "linux-firmware",
        "linux-firmware-nonfree",
        "linux-headers-generic-lts-trusty",
        "linux-image-generic-lts-trusty",
        "lvm2",
        "mcollective",
        "mdadm",
        "nailgun-agent",
        "nailgun-mcagents",
        "nailgun-net-check",
        "ntp",
        "openssh-client",
        "openssh-server",
        "puppet",
        "python-amqp",
        "ruby-augeas",
        "ruby-ipaddress",
        "ruby-json",
        "ruby-netaddr",
        "ruby-openstack",
        "ruby-shadow",
        "ruby-stomp",
        "telnet",
        "ubuntu-minimal",
        "ubuntu-standard",
        "uuid-runtime",
        "vim",
        "virt-what",
        "vlan",
    ]

    def __init__(self, data):
        super(NailgunBuildImage, self).__init__(data)
        self.parse_schemes()
        self.parse_operating_system()

    def parse_operating_system(self):
        if self.data.get('codename').lower() != 'trusty':
            raise errors.WrongInputDataError(
                'Currently, only Ubuntu Trusty is supported, given '
                'codename is {0}'.format(self.data.get('codename')))

        packages = self.data.get('packages', self.DEFAULT_TRUSTY_PACKAGES)

        repos = []
        for repo in self.data['repos']:
            repos.append(objects.DEBRepo(
                name=repo['name'],
                uri=repo['uri'],
                suite=repo['suite'],
                section=repo['section'],
                priority=repo['priority']))

        self.operating_system = objects.Ubuntu(repos=repos, packages=packages)

    def parse_schemes(self):
        self.image_scheme = objects.ImageScheme()
        self.partition_scheme = objects.PartitionScheme()

        for mount, image in six.iteritems(self.data['image_data']):
            filename = os.path.basename(urlsplit(image['uri']).path)
            # Loop does not allocate any loop device
            # during initialization.
            device = objects.Loop()

            self.image_scheme.add_image(
                uri='file://' + os.path.join(self.data['output'], filename),
                format=image['format'],
                container=image['container'],
                target_device=device)

            self.partition_scheme.add_fs(
                device=device,
                mount=mount,
                fs_type=image['format'])

            if mount == '/':
                metadata_filename = filename.split('.', 1)[0] + '.yaml'
                self.metadata_uri = 'file://' + os.path.join(
                    self.data['output'], metadata_filename)
