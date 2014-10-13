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
    def setUp(self):
        super(TestManager, self).setUp()
        self.mgr = manager.Manager(test_nailgun.PROVISION_SAMPLE_DATA)

    @mock.patch.object(hu, 'list_block_devices')
    def test_do_parsing(self, mock_lbd):
        mock_lbd.return_value = test_nailgun.LIST_BLOCK_DEVICES_SAMPLE
        self.mgr.do_parsing()
        #NOTE(agordeev): there's no need for deeper assertions as all schemes
        # thoroughly tested in test_nailgun
        self.assertFalse(self.mgr.partition_scheme is None)
        self.assertFalse(self.mgr.configdrive_scheme is None)
        self.assertFalse(self.mgr.image_scheme is None)

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
                             mock_vgr, mock_lvr, mock_mdr, mock_exec):
        mock_hu_lbd.return_value = test_nailgun.LIST_BLOCK_DEVICES_SAMPLE
        self.mgr.do_parsing()
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
            mock.call('ext4', '', '', '/dev/mapper/os-root'),
            mock.call('swap', '', '', '/dev/mapper/os-swap'),
            mock.call('xfs', '', '', '/dev/mapper/image-glance')]
        self.assertEqual(mock_fu_mf_expected_calls, mock_fu_mf.call_args_list)

    @mock.patch.object(utils, 'execute')
    @mock.patch.object(utils, 'render_and_save')
    @mock.patch.object(hu, 'list_block_devices')
    def test_do_configdrive(self, mock_lbd, mock_u_ras, mock_u_e):
        mock_lbd.return_value = test_nailgun.LIST_BLOCK_DEVICES_SAMPLE
        self.mgr.do_parsing()
        self.assertEqual(1, len(self.mgr.image_scheme.images))
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
        self.assertEqual(2, len(self.mgr.image_scheme.images))
        cf_drv_img = self.mgr.image_scheme.images[-1]
        self.assertEqual('file://%s' % CONF.config_drive_path, cf_drv_img.uri)
        self.assertEqual('/dev/sda7',
                         self.mgr.partition_scheme.configdrive_device())
        self.assertEqual('iso9660', cf_drv_img.format)
        self.assertEqual('raw', cf_drv_img.container)

    @mock.patch.object(partition.PartitionScheme, 'configdrive_device')
    @mock.patch.object(utils, 'execute')
    @mock.patch.object(utils, 'render_and_save')
    @mock.patch.object(hu, 'list_block_devices')
    def test_do_configdrive_no_configdrive_device(self, mock_lbd, mock_u_ras,
                                                  mock_u_e, mock_p_ps_cd):
        mock_lbd.return_value = test_nailgun.LIST_BLOCK_DEVICES_SAMPLE
        self.mgr.do_parsing()
        mock_p_ps_cd.return_value = None
        self.assertRaises(errors.WrongPartitionSchemeError,
                          self.mgr.do_configdrive)

    @mock.patch.object(au, 'GunzipStream')
    @mock.patch.object(au, 'LocalFile')
    @mock.patch.object(au, 'HttpUrl')
    @mock.patch.object(au, 'Chain')
    @mock.patch.object(utils, 'execute')
    @mock.patch.object(utils, 'render_and_save')
    @mock.patch.object(hu, 'list_block_devices')
    def test_do_copyimage(self, mock_lbd, mock_u_ras, mock_u_e, mock_au_c,
                          mock_au_h, mock_au_l, mock_au_g):

        class FakeChain(object):
            processors = []

            def append(self, thing):
                self.processors.append(thing)

            def process(self):
                pass

        mock_lbd.return_value = test_nailgun.LIST_BLOCK_DEVICES_SAMPLE
        mock_au_c.return_value = FakeChain()
        self.mgr.do_parsing()
        self.mgr.do_configdrive()
        self.mgr.do_copyimage()
        imgs = self.mgr.image_scheme.images
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
