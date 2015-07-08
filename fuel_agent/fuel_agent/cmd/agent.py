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

import sys

from oslo.config import cfg
from oslo_serialization import jsonutils as json
import six

from fuel_agent import manager as manager
from fuel_agent.openstack.common import log as logging
from fuel_agent import version

cli_opts = [
    cfg.StrOpt(
        'input_data_file',
        default='/tmp/provision.json',
        help='Input data file'
    ),
    cfg.StrOpt(
        'input_data',
        default='',
        help='Input data (json string)'
    ),
]

CONF = cfg.CONF
CONF.register_cli_opts(cli_opts)


def provision():
    main(['do_provisioning'])


def partition():
    main(['do_partitioning'])


def copyimage():
    main(['do_copyimage'])


def configdrive():
    main(['do_configdrive'])


def bootloader():
    main(['do_bootloader'])


def build_image():
    main(['do_build_image'])


def print_err(line):
    sys.stderr.write(six.text_type(line))
    sys.stderr.write('\n')


def handle_exception(exc):
    LOG = logging.getLogger(__name__)
    LOG.exception(exc)
    print_err('Unexpected error')
    print_err(exc)
    sys.exit(-1)


def main(actions=None):
    CONF(sys.argv[1:], project='fuel-agent',
         version=version.version_info.release_string())

    logging.setup('fuel-agent')
    LOG = logging.getLogger(__name__)

    try:
        if CONF.input_data:
            data = json.loads(CONF.input_data)
        else:
            with open(CONF.input_data_file) as f:
                data = json.load(f)
        LOG.debug('Input data: %s', data)

        mgr = manager.Manager(data)
        if actions:
            for action in actions:
                getattr(mgr, action)()
    except Exception as exc:
        handle_exception(exc)


if __name__ == '__main__':
    main()
