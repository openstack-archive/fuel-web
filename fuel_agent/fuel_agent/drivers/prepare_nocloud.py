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

import jinja2

class NoCloudDriver(object):
    def __init__(self, node_data):
        if isinstance(node_data, (str, unicode)):
            self.node_data = json.loads(node_data)
        else:
            self.node_data = node_data

        cloud_config = {'ssh_auth_key': self.node_data['ks_meta']['auth_key'],
                        'hostname': self.node_data['hostname'],
                        'fqdn': self.node_data['hostname'],
                        'name_servers': self.node_data['name_servers'],
                        'search_domain': self.node_data['name_servers_search'],
                        'master_ip': self.node_data['ks_meta']['mco_host'],
                        'puppet_master': self.node_data['ks_meta']['puppet_master'],
                        'mco_pskey': self.node_data['ks_meta']['mco_pskey'],
                        'mco_vhost': self.node_data['ks_meta']['mco_vhost'],
                        'mco_host': self.node_data['ks_meta']['mco_host'],
                        'mco_user': self.node_data['ks_meta']['mco_user'],
                        'mco_password': self.node_data['ks_meta']['mco_password'],
                        'mco_connector': self.node_data['ks_meta']['mco_connector'],
        }
        boothook = {'udevrules': self.node_data['kernel_options']['udevrules'],
                    'admin_mac': self.node_data['kernel_options']['netcfg/choose_interface']}

        tmpl_path = 'fuel_agent/cloud-init-templates'
        temp_path = '/tmp'
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(tmpl_path))
        template = env.get_template(os.path.join(tmpl_path, 'cloud_config_ubuntu.jinja2'))
        output = template.render({'cloud_config': cloud_config})
        #TODO: ubuntu/centos
        #TODO(agordeev): try/catch?
        with open(os.path.join(temp_path, 'cloud_config.txt'), 'w') as f:
            f.write(output)
        template = env.get_template(os.path.join(tmpl_path, 'boothook_ubuntu.jinja2'))
        output = template.render({'boothook': boothook})
        #TODO(agordeev): try/catch?
        with open(os.path.join(temp_path, 'boothook.txt'), 'w') as f:
            f.write(output)

        # create user-data
        #execute: write-mime-multipart --output=combined-userdata.txt boothook-ubuntu.txt:text/cloud-boothook user-data:text/cloud-config
        # make an image
