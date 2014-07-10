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

import json
import sys

from oslo.config import cfg

from fuel_agent import manager as manager
from fuel_agent.openstack.common import log
from fuel_agent import version

opts = [
    cfg.StrOpt(
        'provision_data_file',
        default='/tmp/provision.json',
        help='Provision data file'
    ),
]

CONF = cfg.CONF
CONF.register_opts(opts)


def main():
    CONF(sys.argv[1:], project='fuel-agent',
         version=version.version_info.release_string())
    log.setup('fuel-agent')

    with open(CONF.provision_data_file) as f:
        data = json.load(f)

    provision_manager = manager.Manager(data)
    provision_manager.do_provisioning()


if __name__ == '__main__':
    main()
