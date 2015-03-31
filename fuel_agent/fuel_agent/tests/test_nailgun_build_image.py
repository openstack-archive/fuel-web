# Copyright 2015 Mirantis, Inc.
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
import six
from six.moves.urllib.parse import urlsplit

from oslotest import base as test_base

from fuel_agent.drivers.nailgun import NailgunBuildImage
from fuel_agent import errors
from fuel_agent import objects

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

REPOS_SAMPLE = [
    {
        "name": "ubuntu",
        "section": "main universe multiverse",
        "uri": "http://archive.ubuntu.com/ubuntu/",
        "priority": None,
        "suite": "trusty",
        "type": "deb"
    },
    {
        "name": "mos",
        "section": "main restricted",
        "uri": "http://10.20.0.2:8080/2014.2-6.1/ubuntu/x86_64",
        "priority": 1050,
        "suite": "mos6.1",
        "type": "deb"
    }
]

IMAGE_DATA_SAMPLE = {
    "/boot": {
        "container": "gzip",
        "uri": "http://10.20.0.2:8080/path/to/img-boot.img.gz",
        "format": "ext2"
    },
    "/": {
        "container": "gzip",
        "uri": "http://10.20.0.2:8080/path/to/img.img.gz",
        "format": "ext4"
    }
}


class TestNailgunBuildImage(test_base.BaseTestCase):

    def test_default_trusty_packages(self):
        self.assertEqual(NailgunBuildImage.DEFAULT_TRUSTY_PACKAGES,
                         DEFAULT_TRUSTY_PACKAGES)

    @mock.patch.object(NailgunBuildImage, '__init__')
    def test_parse_operating_system_error_bad_codename(self, mock_init):
        mock_init.return_value = None
        driver = NailgunBuildImage()
        driver.data = {'codename': 'not-trusty'}
        self.assertRaises(errors.WrongInputDataError,
                          driver.parse_operating_system)

    @mock.patch('fuel_agent.objects.Ubuntu')
    @mock.patch.object(NailgunBuildImage, '__init__')
    def test_parse_operating_system_packages_given(self, mock_init, mock_ub):
        mock_init.return_value = None
        data = {
            'repos': [],
            'codename': 'trusty',
            'packages': ['pack']
        }
        driver = NailgunBuildImage()
        driver.data = data
        mock_ub_instance = mock_ub.return_value
        mock_ub_instance.packages = data['packages']
        driver.parse_operating_system()
        mock_ub.assert_called_once_with(repos=[], packages=data['packages'])
        self.assertEqual(driver.operating_system.packages, data['packages'])

    @mock.patch('fuel_agent.objects.Ubuntu')
    @mock.patch.object(NailgunBuildImage, '__init__')
    def test_parse_operating_system_packages_not_given(
            self, mock_init, mock_ub):
        mock_init.return_value = None
        data = {
            'repos': [],
            'codename': 'trusty'
        }
        driver = NailgunBuildImage()
        driver.data = data
        mock_ub_instance = mock_ub.return_value
        mock_ub_instance.packages = NailgunBuildImage.DEFAULT_TRUSTY_PACKAGES
        driver.parse_operating_system()
        mock_ub.assert_called_once_with(
            repos=[], packages=NailgunBuildImage.DEFAULT_TRUSTY_PACKAGES)
        self.assertEqual(driver.operating_system.packages,
                         NailgunBuildImage.DEFAULT_TRUSTY_PACKAGES)

    @mock.patch('fuel_agent.objects.DEBRepo')
    @mock.patch('fuel_agent.objects.Ubuntu')
    @mock.patch.object(NailgunBuildImage, '__init__')
    def test_parse_operating_system_repos(self, mock_init, mock_ub, mock_deb):
        mock_init.return_value = None
        data = {
            'repos': REPOS_SAMPLE,
            'codename': 'trusty'
        }
        driver = NailgunBuildImage()
        driver.data = data

        mock_deb_expected_calls = []
        repos = []
        for r in REPOS_SAMPLE:
            kwargs = {
                'name': r['name'],
                'uri': r['uri'],
                'suite': r['suite'],
                'section': r['section'],
                'priority': r['priority']
            }
            mock_deb_expected_calls.append(mock.call(**kwargs))
            repos.append(objects.DEBRepo(**kwargs))
        driver.parse_operating_system()
        mock_ub_instance = mock_ub.return_value
        mock_ub_instance.repos = repos
        mock_ub.assert_called_once_with(
            repos=repos, packages=NailgunBuildImage.DEFAULT_TRUSTY_PACKAGES)
        self.assertEqual(mock_deb_expected_calls,
                         mock_deb.call_args_list[:len(REPOS_SAMPLE)])
        self.assertEqual(driver.operating_system.repos, repos)

    @mock.patch('fuel_agent.drivers.nailgun.objects.Loop')
    @mock.patch('fuel_agent.objects.Image')
    @mock.patch('fuel_agent.objects.Fs')
    @mock.patch('fuel_agent.objects.PartitionScheme')
    @mock.patch('fuel_agent.objects.ImageScheme')
    @mock.patch.object(NailgunBuildImage, '__init__')
    def test_parse_schemes(
            self, mock_init, mock_imgsch, mock_partsch,
            mock_fs, mock_img, mock_loop):
        mock_init.return_value = None
        data = {
            'image_data': IMAGE_DATA_SAMPLE,
            'output': '/some/local/path',
        }
        driver = NailgunBuildImage()
        driver.data = data
        driver.parse_schemes()

        mock_fs_expected_calls = []
        mock_img_expected_calls = []
        images = []
        fss = []
        data_length = len(data['image_data'].keys())
        for mount, image in six.iteritems(data['image_data']):
            filename = os.path.basename(urlsplit(image['uri']).path)
            img_kwargs = {
                'uri': 'file://' + os.path.join(data['output'], filename),
                'format': image['format'],
                'container': image['container'],
                'target_device': None
            }
            mock_img_expected_calls.append(mock.call(**img_kwargs))
            images.append(objects.Image(**img_kwargs))

            fs_kwargs = {
                'device': None,
                'mount': mount,
                'fs_type': image['format']
            }
            mock_fs_expected_calls.append(mock.call(**fs_kwargs))
            fss.append(objects.Fs(**fs_kwargs))

            if mount == '/':
                metadata_filename = filename.split('.', 1)[0] + '.yaml'

        mock_imgsch_instance = mock_imgsch.return_value
        mock_imgsch_instance.images = images
        mock_partsch_instance = mock_partsch.return_value
        mock_partsch_instance.fss = fss

        self.assertEqual(
            driver.metadata_uri, 'file://' + os.path.join(
                data['output'], metadata_filename))
        self.assertEqual(mock_img_expected_calls,
                         mock_img.call_args_list[:data_length])
        self.assertEqual(mock_fs_expected_calls,
                         mock_fs.call_args_list[:data_length])
        self.assertEqual(driver.image_scheme.images, images)
        self.assertEqual(driver.partition_scheme.fss, fss)
