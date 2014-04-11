# -*- coding: utf-8 -*-

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

import argparse
import sys
import traceback

from fuel_upgrade.config import config
from fuel_upgrade.logger import configure_logger
logger = configure_logger(config.log_path)

from fuel_upgrade import errors

from fuel_upgrade.upgrade import DockerUpgrader
from fuel_upgrade.upgrade import OpenStackUpgrader
from fuel_upgrade.upgrade import UpgradeManager


#: A dict with supported systems.
#: The key is used for system option in CLI.
SUPPORTED_SYSTEMS = {
    'docker': DockerUpgrader,
    'openstack': OpenStackUpgrader,
}


def handle_exception(exc):
    if isinstance(exc, errors.FuelUpgradeException):
        logger.error(exc)
        sys.exit(-1)
    else:
        traceback.print_exc(exc)
        sys.exit(-1)


def parse_args():
    """Parse arguments and return them
    """
    parser = argparse.ArgumentParser(
        description='fuel-upgrade is an upgrade system for fuel-master node')

    parser.add_argument(
        'systems', choices=SUPPORTED_SYSTEMS.keys(), nargs='+',
        help='systems to upgrade')

    parser.add_argument(
        '--source', required=True,
        help='path to folder with update files')

    parser.add_argument(
        '--no-rollback',
        help='do not rollback in case of errors',
        action='store_true')

    return parser.parse_args()


def run_upgrade(args):
    """Run upgrade on master node
    """
    # create a list of upgraders to be use
    upgraders = [
        SUPPORTED_SYSTEMS[system] for system in args.systems
    ]

    upgrade_manager = UpgradeManager(
        args.source,
        upgraders,
        not args.no_rollback
    )

    upgrade_manager.run()


def main():
    """Entry point
    """
    try:
        run_upgrade(parse_args())
    except Exception as exc:
        handle_exception(exc)
