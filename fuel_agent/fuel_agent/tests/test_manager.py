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

import mock
import os
import signal
import yaml

from oslo.config import cfg
from oslotest import base as test_base

from fuel_agent import errors
from fuel_agent import manager
from fuel_agent.objects import partition
from fuel_agent.tests import test_nailgun
from fuel_agent.utils import artifact_utils as au
from fuel_agent.utils import fs_utils as fu
from fuel_agent.utils import hardware_utils as hu
from fuel_agent.utils import lvm_utils as lu
from fuel_agent.utils import md_utils as mu
from fuel_agent.utils import partition_utils as pu
from fuel_agent.utils import utils

CONF = cfg.CONF


class TestManager(test_base.BaseTestCase):

    @mock.patch('yaml.load')
    @mock.patch.object(utils, 'init_http_request')
    @mock.patch.object(hu, 'list_block_devices')
    def setUp(self, mock_lbd, mock_http, mock_yaml):
        super(TestManager, self).setUp()
        mock_lbd.return_value = test_nailgun.LIST_BLOCK_DEVICES_SAMPLE
        self.mgr = manager.Manager(test_nailgun.PROVISION_SAMPLE_DATA)

    @mock.patch('six.moves.builtins.open')
    @mock.patch.object(os, 'symlink')
    @mock.patch.object(os, 'remove')
    @mock.patch.object(os, 'path')
    @mock.patch.object(os, 'listdir')
    @mock.patch.object(utils, 'execute')
    @mock.patch.object(mu, 'mdclean_all')
    @mock.patch.object(lu, 'lvremove_all')
    @mock.patch.object(lu, 'vgremove_all')
    @mock.patch.object(lu, 'pvremove_all')
    @mock.patch.object(fu, 'make_fs')
    @mock.patch.object(lu, 'lvcreate')
    @mock.patch.object(lu, 'vgcreate')
    @mock.patch.object(lu, 'pvcreate')
    @mock.patch.object(mu, 'mdcreate')
    @mock.patch.object(pu, 'set_gpt_type')
    @mock.patch.object(pu, 'set_partition_flag')
    @mock.patch.object(pu, 'make_partition')
    @mock.patch.object(pu, 'make_label')
    @mock.patch.object(hu, 'list_block_devices')
    def test_do_partitioning(self, mock_hu_lbd, mock_pu_ml, mock_pu_mp,
                             mock_pu_spf, mock_pu_sgt, mock_mu_m, mock_lu_p,
                             mock_lu_v, mock_lu_l, mock_fu_mf, mock_pvr,
                             mock_vgr, mock_lvr, mock_mdr, mock_exec,
                             mock_os_ld, mock_os_p, mock_os_r, mock_os_s,
                             mock_open):
        mock_os_ld.return_value = ['not_a_rule', 'fake.rules']
        mock_os_p.exists.return_value = True
        mock_hu_lbd.return_value = test_nailgun.LIST_BLOCK_DEVICES_SAMPLE
        self.mgr.do_partitioning()
        mock_pu_ml_expected_calls = [mock.call('/dev/sda', 'gpt'),
                                     mock.call('/dev/sdb', 'gpt'),
                                     mock.call('/dev/sdc', 'gpt')]
        self.assertEqual(mock_pu_ml_expected_calls, mock_pu_ml.call_args_list)

        mock_pu_mp_expected_calls = [
            mock.call('/dev/sda', 1, 25, 'primary'),
            mock.call('/dev/sda', 25, 225, 'primary'),
            mock.call('/dev/sda', 225, 425, 'primary'),
            mock.call('/dev/sda', 425, 625, 'primary'),
            mock.call('/dev/sda', 625, 20063, 'primary'),
            mock.call('/dev/sda', 20063, 65660, 'primary'),
            mock.call('/dev/sda', 65660, 65680, 'primary'),
            mock.call('/dev/sdb', 1, 25, 'primary'),
            mock.call('/dev/sdb', 25, 225, 'primary'),
            mock.call('/dev/sdb', 225, 425, 'primary'),
            mock.call('/dev/sdb', 425, 65396, 'primary'),
            mock.call('/dev/sdc', 1, 25, 'primary'),
            mock.call('/dev/sdc', 25, 225, 'primary'),
            mock.call('/dev/sdc', 225, 425, 'primary'),
            mock.call('/dev/sdc', 425, 65396, 'primary')]
        self.assertEqual(mock_pu_mp_expected_calls, mock_pu_mp.call_args_list)

        mock_pu_spf_expected_calls = [mock.call('/dev/sda', 1, 'bios_grub'),
                                      mock.call('/dev/sdb', 1, 'bios_grub'),
                                      mock.call('/dev/sdc', 1, 'bios_grub')]
        self.assertEqual(mock_pu_spf_expected_calls,
                         mock_pu_spf.call_args_list)

        mock_pu_sgt_expected_calls = [mock.call('/dev/sda', 4, 'fake_guid')]
        self.assertEqual(mock_pu_sgt_expected_calls,
                         mock_pu_sgt.call_args_list)

        mock_mu_m_expected_calls = [mock.call('/dev/md0', 'mirror',
                                              '/dev/sda3', '/dev/sdb3',
                                              '/dev/sdc3')]
        self.assertEqual(mock_mu_m_expected_calls, mock_mu_m.call_args_list)

        mock_lu_p_expected_calls = [
            mock.call('/dev/sda5', metadatasize=28, metadatacopies=2),
            mock.call('/dev/sda6', metadatasize=28, metadatacopies=2),
            mock.call('/dev/sdb4', metadatasize=28, metadatacopies=2),
            mock.call('/dev/sdc4', metadatasize=28, metadatacopies=2)]
        self.assertEqual(mock_lu_p_expected_calls, mock_lu_p.call_args_list)

        mock_lu_v_expected_calls = [mock.call('os', '/dev/sda5'),
                                    mock.call('image', '/dev/sda6',
                                              '/dev/sdb4', '/dev/sdc4')]
        self.assertEqual(mock_lu_v_expected_calls, mock_lu_v.call_args_list)

        mock_lu_l_expected_calls = [mock.call('os', 'root', 15360),
                                    mock.call('os', 'swap', 4014),
                                    mock.call('image', 'glance', 175347)]
        self.assertEqual(mock_lu_l_expected_calls, mock_lu_l.call_args_list)

        mock_fu_mf_expected_calls = [
            mock.call('ext2', '', '', '/dev/md0'),
            mock.call('ext2', '', '', '/dev/sda4'),
            mock.call('swap', '', '', '/dev/mapper/os-swap'),
            mock.call('xfs', '', '', '/dev/mapper/image-glance')]
        self.assertEqual(mock_fu_mf_expected_calls, mock_fu_mf.call_args_list)

    @mock.patch.object(utils, 'calculate_md5')
    @mock.patch('os.path.getsize')
    @mock.patch('yaml.load')
    @mock.patch.object(utils, 'init_http_request')
    @mock.patch.object(utils, 'execute')
    @mock.patch.object(utils, 'render_and_save')
    @mock.patch.object(hu, 'list_block_devices')
    def test_do_configdrive(self, mock_lbd, mock_u_ras, mock_u_e,
                            mock_http_req, mock_yaml, mock_get_size, mock_md5):
        mock_get_size.return_value = 123
        mock_md5.return_value = 'fakemd5'
        mock_lbd.return_value = test_nailgun.LIST_BLOCK_DEVICES_SAMPLE
        self.assertEqual(1, len(self.mgr.driver.image_scheme.images))
        self.mgr.do_configdrive()
        mock_u_ras_expected_calls = [
            mock.call(CONF.nc_template_path,
                      ['cloud_config_pro_fi-le.jinja2',
                       'cloud_config_pro.jinja2',
                       'cloud_config_pro_fi.jinja2',
                       'cloud_config.jinja2'],
                      mock.ANY, '%s/%s' % (CONF.tmp_path, 'cloud_config.txt')),
            mock.call(CONF.nc_template_path,
                      ['boothook_pro_fi-le.jinja2',
                       'boothook_pro.jinja2',
                       'boothook_pro_fi.jinja2',
                       'boothook.jinja2'],
                      mock.ANY, '%s/%s' % (CONF.tmp_path, 'boothook.txt')),
            mock.call(CONF.nc_template_path,
                      ['meta-data_pro_fi-le.jinja2',
                       'meta-data_pro.jinja2',
                       'meta-data_pro_fi.jinja2',
                       'meta-data.jinja2'],
                      mock.ANY, '%s/%s' % (CONF.tmp_path, 'meta-data'))]
        self.assertEqual(mock_u_ras_expected_calls, mock_u_ras.call_args_list)

        mock_u_e_expected_calls = [
            mock.call('write-mime-multipart',
                      '--output=%s' % ('%s/%s' % (CONF.tmp_path, 'user-data')),
                      '%s:text/cloud-boothook' % ('%s/%s' % (CONF.tmp_path,
                                                             'boothook.txt')),
                      '%s:text/cloud-config' % ('%s/%s' % (CONF.tmp_path,
                                                           'cloud_config.txt'))
                      ),
            mock.call('genisoimage', '-output', CONF.config_drive_path,
                      '-volid', 'cidata', '-joliet', '-rock',
                      '%s/%s' % (CONF.tmp_path, 'user-data'),
                      '%s/%s' % (CONF.tmp_path, 'meta-data'))]
        self.assertEqual(mock_u_e_expected_calls, mock_u_e.call_args_list)
        self.assertEqual(2, len(self.mgr.driver.image_scheme.images))
        cf_drv_img = self.mgr.driver.image_scheme.images[-1]
        self.assertEqual('file://%s' % CONF.config_drive_path, cf_drv_img.uri)
        self.assertEqual('/dev/sda7',
                         self.mgr.driver.partition_scheme.configdrive_device())
        self.assertEqual('iso9660', cf_drv_img.format)
        self.assertEqual('raw', cf_drv_img.container)
        self.assertEqual('fakemd5', cf_drv_img.md5)
        self.assertEqual(123, cf_drv_img.size)

    @mock.patch('yaml.load')
    @mock.patch.object(utils, 'init_http_request')
    @mock.patch.object(partition.PartitionScheme, 'configdrive_device')
    @mock.patch.object(utils, 'execute')
    @mock.patch.object(utils, 'render_and_save')
    @mock.patch.object(hu, 'list_block_devices')
    def test_do_configdrive_no_configdrive_device(self, mock_lbd, mock_u_ras,
                                                  mock_u_e, mock_p_ps_cd,
                                                  mock_http_req, mock_yaml):
        mock_lbd.return_value = test_nailgun.LIST_BLOCK_DEVICES_SAMPLE
        mock_p_ps_cd.return_value = None
        self.assertRaises(errors.WrongPartitionSchemeError,
                          self.mgr.do_configdrive)

    @mock.patch.object(utils, 'calculate_md5')
    @mock.patch('os.path.getsize')
    @mock.patch('yaml.load')
    @mock.patch.object(utils, 'init_http_request')
    @mock.patch.object(fu, 'extend_fs')
    @mock.patch.object(au, 'GunzipStream')
    @mock.patch.object(au, 'LocalFile')
    @mock.patch.object(au, 'HttpUrl')
    @mock.patch.object(au, 'Chain')
    @mock.patch.object(utils, 'execute')
    @mock.patch.object(utils, 'render_and_save')
    @mock.patch.object(hu, 'list_block_devices')
    def test_do_copyimage(self, mock_lbd, mock_u_ras, mock_u_e, mock_au_c,
                          mock_au_h, mock_au_l, mock_au_g, mock_fu_ef,
                          mock_http_req, mock_yaml, mock_get_size, mock_md5):

        class FakeChain(object):
            processors = []

            def append(self, thing):
                self.processors.append(thing)

            def process(self):
                pass

        mock_lbd.return_value = test_nailgun.LIST_BLOCK_DEVICES_SAMPLE
        mock_au_c.return_value = FakeChain()
        self.mgr.do_configdrive()
        self.mgr.do_copyimage()
        imgs = self.mgr.driver.image_scheme.images
        self.assertEqual(2, len(imgs))
        expected_processors_list = []
        for img in imgs[:-1]:
            expected_processors_list += [
                img.uri,
                au.HttpUrl,
                au.GunzipStream,
                img.target_device
            ]
        expected_processors_list += [
            imgs[-1].uri,
            au.LocalFile,
            imgs[-1].target_device
        ]
        self.assertEqual(expected_processors_list,
                         mock_au_c.return_value.processors)
        mock_fu_ef_expected_calls = [
            mock.call('ext4', '/dev/mapper/os-root')]
        self.assertEqual(mock_fu_ef_expected_calls, mock_fu_ef.call_args_list)

    @mock.patch.object(utils, 'calculate_md5')
    @mock.patch('os.path.getsize')
    @mock.patch('yaml.load')
    @mock.patch.object(utils, 'init_http_request')
    @mock.patch.object(fu, 'extend_fs')
    @mock.patch.object(au, 'GunzipStream')
    @mock.patch.object(au, 'LocalFile')
    @mock.patch.object(au, 'HttpUrl')
    @mock.patch.object(au, 'Chain')
    @mock.patch.object(utils, 'execute')
    @mock.patch.object(utils, 'render_and_save')
    @mock.patch.object(hu, 'list_block_devices')
    def test_do_copyimage_md5_matches(self, mock_lbd, mock_u_ras, mock_u_e,
                                      mock_au_c, mock_au_h, mock_au_l,
                                      mock_au_g, mock_fu_ef, mock_http_req,
                                      mock_yaml, mock_get_size, mock_md5):

        class FakeChain(object):
            processors = []

            def append(self, thing):
                self.processors.append(thing)

            def process(self):
                pass

        mock_get_size.return_value = 123
        mock_md5.side_effect = ['fakemd5', 'really_fakemd5', 'fakemd5']
        mock_lbd.return_value = test_nailgun.LIST_BLOCK_DEVICES_SAMPLE
        mock_au_c.return_value = FakeChain()
        self.mgr.driver.image_scheme.images[0].size = 1234
        self.mgr.driver.image_scheme.images[0].md5 = 'really_fakemd5'
        self.mgr.do_configdrive()
        self.assertEqual(2, len(self.mgr.driver.image_scheme.images))
        self.mgr.do_copyimage()
        expected_md5_calls = [mock.call('/tmp/config-drive.img', 123),
                              mock.call('/dev/mapper/os-root', 1234),
                              mock.call('/dev/sda7', 123)]
        self.assertEqual(expected_md5_calls, mock_md5.call_args_list)

    @mock.patch.object(utils, 'calculate_md5')
    @mock.patch('os.path.getsize')
    @mock.patch('yaml.load')
    @mock.patch.object(utils, 'init_http_request')
    @mock.patch.object(fu, 'extend_fs')
    @mock.patch.object(au, 'GunzipStream')
    @mock.patch.object(au, 'LocalFile')
    @mock.patch.object(au, 'HttpUrl')
    @mock.patch.object(au, 'Chain')
    @mock.patch.object(utils, 'execute')
    @mock.patch.object(utils, 'render_and_save')
    @mock.patch.object(hu, 'list_block_devices')
    def test_do_copyimage_md5_mismatch(self, mock_lbd, mock_u_ras, mock_u_e,
                                       mock_au_c, mock_au_h, mock_au_l,
                                       mock_au_g, mock_fu_ef, mock_http_req,
                                       mock_yaml, mock_get_size, mock_md5):

        class FakeChain(object):
            processors = []

            def append(self, thing):
                self.processors.append(thing)

            def process(self):
                pass

        mock_get_size.return_value = 123
        mock_md5.side_effect = ['fakemd5', 'really_fakemd5', 'fakemd5']
        mock_lbd.return_value = test_nailgun.LIST_BLOCK_DEVICES_SAMPLE
        mock_au_c.return_value = FakeChain()
        self.mgr.driver.image_scheme.images[0].size = 1234
        self.mgr.driver.image_scheme.images[0].md5 = 'fakemd5'
        self.mgr.do_configdrive()
        self.assertEqual(2, len(self.mgr.driver.image_scheme.images))
        self.assertRaises(errors.ImageChecksumMismatchError,
                          self.mgr.do_copyimage)

    @mock.patch('fuel_agent.utils.build_utils.add_apt_preference')
    @mock.patch('fuel_agent.utils.build_utils.add_apt_source')
    @mock.patch('fuel_agent.utils.build_utils.attach_file_to_loop')
    @mock.patch('fuel_agent.utils.build_utils.containerize')
    @mock.patch('fuel_agent.utils.build_utils.create_sparsed_tmp_file')
    @mock.patch('fuel_agent.utils.build_utils.deattach_loop')
    @mock.patch('fuel_agent.utils.build_utils.do_post_inst')
    @mock.patch('fuel_agent.utils.build_utils.get_free_loop')
    @mock.patch('fuel_agent.utils.build_utils.pre_apt_get')
    @mock.patch('fuel_agent.utils.build_utils.run_apt_get')
    @mock.patch('fuel_agent.utils.build_utils.run_debootstrap')
    @mock.patch('fuel_agent.utils.build_utils.set_apt_get_env')
    @mock.patch('fuel_agent.utils.build_utils.shrink_sparse_file')
    @mock.patch('fuel_agent.utils.build_utils.signal_chrooted_processes')
    @mock.patch('fuel_agent.utils.build_utils.suppress_services_start')
    @mock.patch('fuel_agent.utils.fs_utils.make_fs')
    @mock.patch('fuel_agent.utils.fs_utils.mount_bind')
    @mock.patch('fuel_agent.utils.fs_utils.umount_fs')
    @mock.patch('fuel_agent.utils.utils.calculate_md5')
    @mock.patch('os.makedirs')
    @mock.patch('os.path.exists')
    @mock.patch('os.path.getsize')
    @mock.patch('os.path.isdir')
    @mock.patch('shutil.move')
    @mock.patch('six.moves.builtins.open', create=True, new_callable=mock.mock_open)
    @mock.patch('tempfile.mkdtemp')
    @mock.patch('time.sleep')
    @mock.patch.object(manager.Manager, 'mount_target')
    @mock.patch.object(manager.Manager, 'umount_target')
    def test_do_build_image(self,
                            mock_umount_target,
                            mock_mount_target,
                            mock_sleep,
                            mock_mkdtemp,
                            mock_open,
                            mock_shutil_move,
                            mock_os_path_isdir,
                            mock_os_path_getsize,
                            mock_os_path_exists,
                            mock_os_makedirs,
                            mock_md5,
                            mock_umount_fs,
                            mock_mount_bind,
                            mock_makefs,
                            mock_serv_start,
                            mock_sign_proc,
                            mock_shrink,
                            mock_apt_env,
                            mock_deboot,
                            mock_run_apt,
                            mock_pre_apt,
                            mock_free_loop,
                            mock_post_inst,
                            mock_detach_loop,
                            mock_sparse,
                            mock_containerize,
                            mock_attach,
                            mock_apt_src,
                            mock_apt_pref,
                            ):

        class FakeLoop(object):
            name = None

            def __str__(self):
                return str(self.name)

        loops = [FakeLoop(), FakeLoop()]

        class FakeImage(object):
            def __init__(self, uri, container, target_device, format):
                self.uri = uri
                self.container = container
                self.target_device = target_device
                self.format = format

        class FakeImageScheme(object):
            images = [
                FakeImage('file:///fake/img.img.gz', 'gzip',
                          loops[0], 'ext4'),
                FakeImage('file:///fake/img-boot.img.gz', 'gzip',
                          loops[1], 'ext2')
            ]

        class FakeRepo(object):
            def __init__(self, name, uri, suite, section, priority=None):
                self.name = name
                self.uri = uri
                self.suite = suite
                self.section = section
                self.priority = priority
                self.meta = None

        class FakeOS(object):
            repos = [
                FakeRepo('ubuntu', 'http://fakeubuntu',
                         'trusty', 'fakesection'),
                FakeRepo('mos', 'http://fakemos',
                         'mosX.Y', 'fakesection', 1000)
            ]
            packages = ['fakepackage1', 'fakepackage2']

        class FakeFs(object):
            def __init__(self, mount, type, device):
                self.mount = mount
                self.type = type
                self.device = device
                self.options = ''
                self.label = ''

        class FakePartitionScheme(object):
            fss = [
                FakeFs('/', 'ext4', loops[0]),
                FakeFs('/boot', 'ext2', loops[1])
            ]

            def fs_by_device(self, device):
                found = filter(lambda x: x.device == device, self.fss)
                if found:
                    return found[0]

        self.mgr.driver.image_scheme = FakeImageScheme()
        self.mgr.driver.partition_scheme = FakePartitionScheme()
        self.mgr.driver.metadata_uri = 'file:///fake/img.yaml'
        self.mgr.driver.operating_system = FakeOS()

        mock_os_path_exists.return_value = False
        mock_sparse.side_effect = ['/tmp/img', '/tmp/img-boot']
        mock_free_loop.side_effect = ['/dev/loop0', '/dev/loop1']
        mock_mkdtemp.return_value = '/tmp/imgdir'
        mock_os_path_isdir.return_value = True
        mock_os_path_getsize_side = [20, 2, 10, 1]
        mock_os_path_getsize.side_effect = mock_os_path_getsize_side
        mock_md5_side = ['fakemd5_raw', 'fakemd5_gzip',
                         'fakemd5_raw_boot', 'fakemd5_gzip_boot']
        mock_md5.side_effect = mock_md5_side
        mock_containerize.side_effect = ['/tmp/img.gz', '/tmp/img-boot.gz']

        self.mgr.do_build_image()
        self.assertEqual(
            [mock.call('/fake/img.img.gz'),
             mock.call('/fake/img-boot.img.gz')],
            mock_os_path_exists.call_args_list)
        self.assertEqual([mock.call(dir=CONF.image_build_dir,
                                    suffix=CONF.image_build_suffix)] * 2,
                         mock_sparse.call_args_list)
        self.assertEqual([mock.call()] * 2, mock_free_loop.call_args_list)
        self.assertEqual([mock.call('/dev/loop0', '/tmp/img'),
                          mock.call('/dev/loop1', '/tmp/img-boot')],
                         mock_attach.call_args_list)
        self.assertEqual([mock.call(fs_type='ext4', fs_options='',
                                    fs_label='', dev='/dev/loop0'),
                          mock.call(fs_type='ext2', fs_options='',
                                    fs_label='', dev='/dev/loop1')],
                         mock_makefs.call_args_list)
        mock_mkdtemp.assert_called_once_with(dir=CONF.image_build_dir,
                                             suffix=CONF.image_build_suffix)
        mock_mount_target.assert_called_once_with(
            '/tmp/imgdir', treat_mtab=False, pseudo=False)
        self.assertEqual([mock.call('/tmp/imgdir')] * 2,
                         mock_serv_start.call_args_list)
        mock_deboot.assert_called_once_with(
            uri='http://fakeubuntu', suite='trusty', chroot='/tmp/imgdir')
        mock_apt_env.assert_called_once_with()
        mock_pre_apt.assert_called_once_with('/tmp/imgdir')
        self.assertEqual([
            mock.call(name='ubuntu',
                      uri='http://fakeubuntu',
                      suite='trusty',
                      section='fakesection',
                      chroot='/tmp/imgdir'),
            mock.call(name='mos',
                      uri='http://fakemos',
                      suite='mosX.Y',
                      section='fakesection',
                      chroot='/tmp/imgdir')], mock_apt_src.call_args_list)
        self.assertEqual([
            mock.call(name='ubuntu',
                      priority=None,
                      suite='trusty',
                      section='fakesection',
                      chroot='/tmp/imgdir'),
            mock.call(name='mos',
                      priority=1000,
                      suite='mosX.Y',
                      section='fakesection',
                      chroot='/tmp/imgdir')], mock_apt_pref.call_args_list)
        mock_os_path_isdir.assert_called_once_with('/tmp/imgdir/proc')
        mock_mount_bind.assert_called_once_with('/tmp/imgdir', '/proc')
        mock_run_apt.assert_called_once_with(
            '/tmp/imgdir', packages=['fakepackage1', 'fakepackage2'])
        mock_post_inst.assert_called_once_with('/tmp/imgdir')
        self.assertEqual([mock.call('/tmp/imgdir', signal.SIGTERM),
                          mock.call('/tmp/imgdir', signal.SIGKILL)],
                         mock_sign_proc.call_args_list)
        mock_sleep.assert_called_once_with(2)
        mock_umount_fs.assert_called_once_with('/tmp/imgdir/proc')
        mock_umount_target.assert_called_once_with('/tmp/imgdir', pseudo=False)
        self.assertEqual([mock.call('/dev/loop0'), mock.call('/dev/loop1')],
                         mock_detach_loop.call_args_list)
        self.assertEqual([mock.call('/tmp/img'), mock.call('/tmp/img-boot')],
                         mock_shrink.call_args_list)
        self.assertEqual([mock.call('/tmp/img'),
                          mock.call('/fake/img.img.gz'),
                          mock.call('/tmp/img-boot'),
                          mock.call('/fake/img-boot.img.gz')],
                         mock_os_path_getsize.call_args_list)
        self.assertEqual([mock.call('/tmp/img', 20),
                          mock.call('/fake/img.img.gz', 2),
                          mock.call('/tmp/img-boot', 10),
                          mock.call('/fake/img-boot.img.gz', 1)],
                         mock_md5.call_args_list)
        self.assertEqual([mock.call('/tmp/img', 'gzip'),
                          mock.call('/tmp/img-boot', 'gzip')],
                         mock_containerize.call_args_list)
        mock_open.assert_called_once_with('/fake/img.yaml', 'w')
        self.assertEqual(
            [mock.call('/tmp/img.gz', '/fake/img.img.gz'),
             mock.call('/tmp/img-boot.gz', '/fake/img-boot.img.gz')],
            mock_shutil_move.call_args_list)

        metadata = {}
        for repo in self.mgr.driver.operating_system.repos:
            metadata.setdefault('repos', []).append({
                'type': 'deb',
                'name': repo.name,
                'uri': repo.uri,
                'suite': repo.suite,
                'section': repo.section,
                'priority': repo.priority,
                'meta': repo.meta})
        metadata['packages'] = self.mgr.driver.operating_system.packages
        metadata['images'] = [
            {
                'raw_md5': mock_md5_side[0],
                'raw_size': mock_os_path_getsize_side[0],
                'raw_name': None,
                'container_name':
                os.path.basename(
                    self.mgr.driver.image_scheme.images[0].uri.split(
                        'file://', 1)[1]),
                'container_md5': mock_md5_side[1],
                'container_size': mock_os_path_getsize_side[1],
                'container': self.mgr.driver.image_scheme.images[0].container,
                'format': self.mgr.driver.image_scheme.images[0].format
            },
            {
                'raw_md5': mock_md5_side[2],
                'raw_size': mock_os_path_getsize_side[2],
                'raw_name': None,
                'container_name':
                os.path.basename(
                    self.mgr.driver.image_scheme.images[1].uri.split(
                        'file://', 1)[1]),
                'container_md5': mock_md5_side[3],
                'container_size': mock_os_path_getsize_side[3],
                'container': self.mgr.driver.image_scheme.images[1].container,
                'format': self.mgr.driver.image_scheme.images[1].format
            }
        ]
        mock_open().write.assert_called_once_with(yaml.safe_dump(metadata))
