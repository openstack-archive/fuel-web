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

import json
import os

import jinja2
from oslo.config import cfg

from fuel_agent.utils import utils


no_cloud_opts = [
    cfg.StrOpt(
        'nc_template_path',
        default='/usr/share/fuel-agent/cloud-init-templates',
        help='Path to directory with cloud init templates',
    ),
    cfg.StrOpt(
        'nc_cc_ubuntu_name',
        default='cloud_config_ubuntu.jinja2',
        help='Ubuntu cloud config template name',
    ),
    cfg.StrOpt(
        'nc_bh_ubuntu_name',
        default='boothook_ubuntu.jinja2',
        help='Ubuntu boothook template name',
    ),
    cfg.StrOpt(
        'tmp_path',
        default='/tmp',
        help='Temporary directory for file manipulations',
    ),
    cfg.StrOpt(
        'node_provision_data_path',
        default='/tmp/provision.json',
        help='Path to JSON formatted file with node provision data',
    ),
    cfg.StrOpt(
        'config_drive_path',
        default='/tmp/config-drive.img',
        help='Path where to store generated config drive image',
    ),
]

CONF = cfg.CONF
CONF.register_opts(no_cloud_opts)


class NoCloudDriver(object):

    def __init__(self):
        try:
            with open(CONF.node_provision_data_path) as f:
                self.node_data = json.load(f)
        except Exception as e:
            raise Exception('Something goes wrong while trying to access or '
                            'parse json-data file')

        cloud_config = {'ssh_auth_key': self.node_data['ks_meta']['auth_key'],
                        'hostname': self.node_data['hostname'],
                        'fqdn': self.node_data['hostname'],
                        'name_servers': self.node_data['name_servers'],
                        'search_domain': self.node_data['name_servers_search'],
                        # TODO(agordeev): very ugly, but should work
                        'master_ip': self.node_data['ks_meta']['mco_host'],
                        'puppet_master': self.node_data['ks_meta']
                        ['puppet_master'],
                        'mco_pskey': self.node_data['ks_meta']['mco_pskey'],
                        'mco_vhost': self.node_data['ks_meta']['mco_vhost'],
                        'mco_host': self.node_data['ks_meta']['mco_host'],
                        'mco_user': self.node_data['ks_meta']['mco_user'],
                        'mco_password': self.node_data['ks_meta']
                        ['mco_password'],
                        'mco_connector': self.node_data['ks_meta']
                        ['mco_connector'],
                        }
        boothook = {'udevrules': self.node_data['kernel_options']['udevrules'],
                    'admin_mac': self.node_data['kernel_options']
                    ['netcfg/choose_interface'],
                    # TODO(agordeev): very ugly construction, but should work
                    'server': self.node_data['ks_meta']['mco_host']}

        cc_output_path = os.path.join(CONF.tmp_path, 'cloud_config.txt')
        bh_output_path = os.path.join(CONF.tmp_path, 'boothook.txt')
        # NOTE:file should be strictly named as 'user-data'
        ud_output_path = os.path.join(CONF.tmp_path, 'user-data')
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(CONF.nc_template_path))
        template = env.get_template(CONF.nc_cc_ubuntu_name)
        output = template.render({'cloud_config': cloud_config})
        # TODO: ubuntu/centos
        # TODO(agordeev): try/catch?
        with open(cc_output_path, 'w') as f:
            f.write(output)
        template = env.get_template(CONF.nc_bh_ubuntu_name)
        output = template.render({'boothook': boothook})
        # TODO(agordeev): try/catch?
        with open(bh_output_path, 'w') as f:
            f.write(output)

        utils.execute('write-mime-multipart', '--output=%s' % ud_output_path,
                      '%s:text/cloud-boothook' % bh_output_path,
                      '%s:text/cloud-config' % cc_output_path)
        utils.execute('genisoimage', '-output', CONF.config_drive_path,
                      '-volid', 'cidata', '-joliet', '-rock', ud_output_path)
