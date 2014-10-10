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

import hashlib
import json
import time

from fuel_agent_ci.tests import base
from fuel_agent_ci import utils


class TestConfigDrive(base.BaseFuelAgentCITest):

    def _build_configdrive(self, profile):
        data = json.loads(self.render_template(
            template_name='provision.json',
            template_data={
                'IP': self.dhcp_hosts[0]['ip'],
                'MAC': self.dhcp_hosts[0]['mac'],
                'MASTER_IP': self.net.ip,
                'MASTER_HTTP_PORT': self.http.port,
                'PROFILE': profile,
            }
        ))
        self.ssh.put_content(json.dumps(data), '/tmp/provision.json')

        admin_interface = filter(
            lambda x: (x['mac_address'] ==
                       data['kernel_options']['netcfg/choose_interface']),
            [dict(name=name, **spec) for name, spec
             in data['interfaces'].iteritems()])[0]

        with open('/tmp/boothook.txt', 'wb') as f:
            f.write(self.render_template(
                template_name='boothook_%s.jinja2' % profile.split('_')[0],
                template_data={
                    'MASTER_IP': data['ks_meta']['master_ip'],
                    'ADMIN_MAC': \
                        data['kernel_options']['netcfg/choose_interface'],
                    'UDEVRULES': data['kernel_options']['udevrules']
                }
            ))

        with open('/tmp/cloud_config.txt', 'wb') as f:
            f.write(self.render_template(
                template_name='cloud_config_%s.jinja2' % profile.split('_')[0],
                template_data={
                    'SSH_AUTH_KEY': data['ks_meta']['auth_key'],
                    'TIMEZONE': data['ks_meta']['timezone'],
                    'HOSTNAME': data['hostname'],
                    'FQDN': data['hostname'],
                    'NAME_SERVERS': data['name_servers'],
                    'SEARCH_DOMAIN': data['name_servers_search'],
                    'MASTER_IP': data['ks_meta']['master_ip'],
                    'MASTER_URL': \
                        'http://%s:8000/api' % data['ks_meta']['master_ip'],
                    # FIXME(kozhukalov):
                    # 'KS_REPOS': IS NOT SET YET,
                    'MCO_PSKEY': data['ks_meta']['mco_pskey'],
                    'MCO_CONNECTOR': data['ks_meta']['mco_connector'],
                    'MCO_VHOST': data['ks_meta']['mco_vhost'],
                    'MCO_HOST': data['ks_meta']['mco_host'],
                    # 'MCO_PORT': IS NOT SET, DEFAULT IS USED
                    'MCO_USER': data['ks_meta']['mco_user'],
                    'MCO_PASSWORD': data['ks_meta']['mco_password'],
                    'PUPPET_MASTER': data['ks_meta']['puppet_master']
                }
            ))

        with open('/tmp/meta-data', 'wb') as f:
            f.write(self.render_template(
                template_name='meta-data_%s.jinja2' % profile.split('_')[0],
                template_data={
                    'ADMIN_IFACE_NAME': admin_interface['name'],
                    'ADMIN_IP': admin_interface['ip_address'],
                    'ADMIN_MASK': admin_interface['netmask'],
                    'HOSTNAME': data['hostname']
                }
            ))

        # write-mime-multipart is provided by cloud-utils package
        utils.execute('write-mime-multipart --output=/tmp/user-data '
                      '/tmp/boothook.txt:text/cloud-boothook '
                      '/tmp/cloud_config.txt:text/cloud-config')

        # That does not make sense to build config-drive.img as we can not
        # use it as a reference for comparing md5 sum.
        # The reason for that is that write-mime-multipart generates
        # random boundary identifier in the beginning of user-data.

    def _test_configdrive(self, profile):
        def _get_md5sum(file_path, size=-1):
            md5 = None
            with open(file_path) as f:
                md5 = hashlib.md5(f.read(size)).hexdigest()
            return md5

        self._build_configdrive(profile)
        self.ssh.run('configdrive')
        self.ssh.get_file('/tmp/config-drive.img',
                          '/tmp/actual-config-drive.img')

        # checking configdrive file system type
        fs_type = utils.execute(
            'blkid -o value -s TYPE /tmp/actual-config-drive.img')
        self.assertEqual('iso9660', str(fs_type).strip())

        # checking configdrive label
        label_output = utils.execute(
            'blkid -o value -s LABEL /tmp/actual-config-drive.img')
        self.assertEqual('cidata', str(label_output).strip())

        # mounting configdrive to check its content
        utils.execute('mkdir -p /tmp/cfgdrv')
        utils.execute('sudo mount -o loop '
                      '/tmp/actual-config-drive.img /tmp/cfgdrv')

        #NOTE(agordeev): mime boundary should be the same in both files,
        #                since boundary is always randomly generated,
        #                thus magic prevents from checksum differencies
        with open('/tmp/user-data') as f:
            expected_boundary = f.read().split('\n')[0].split('"')[1]
        actual_boundary = str(utils.execute(
            'head -n1 /tmp/cfgdrv/user-data')).split('"')[1]
        actual_md5_userdata = str(utils.execute(
            'sed -e s/%s/%s/ %s | md5sum' %
            (actual_boundary, expected_boundary,
             '/tmp/cfgdrv/user-data'))).split()[0]
        actual_md5_metadata = str(utils.execute(
            'md5sum /tmp/cfgdrv/meta-data')).split()[0]

        # getting reference md5 for user-data and meta-data
        md5_userdata = _get_md5sum('/tmp/user-data')
        md5_metadata = _get_md5sum('/tmp/meta-data')

        self.assertEqual(md5_userdata, actual_md5_userdata)
        self.assertEqual(md5_metadata, actual_md5_metadata)

    def test_configdrive_centos(self):
        self._test_configdrive('centos_65_x86_64')

    def test_configdrive_ubuntu(self):
        self._test_configdrive('ubuntu_1204_x86_64')

    def tearDown(self):
        utils.execute('sudo umount -f /tmp/cfgdrv')
        utils.execute('rm /tmp/actual-config-drive.img '
                      '/tmp/user-data /tmp/meta-data '
                      '/tmp/cloud_config.txt /tmp/boothook.txt')
        super(TestConfigDrive, self).tearDown()
