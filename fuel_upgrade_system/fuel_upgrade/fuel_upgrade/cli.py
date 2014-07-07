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

from fuel_upgrade.logger import configure_logger
logger = configure_logger('/var/log/fuel_upgrade.log')

from fuel_upgrade.config import build_config
from fuel_upgrade.upgrade import UpgradeManager

from fuel_upgrade.engines.bootstrap import BootstrapUpgrader
from fuel_upgrade.engines.docker_engine import DockerInitializer
from fuel_upgrade.engines.docker_engine import DockerUpgrader
from fuel_upgrade.engines.host_system import HostSystemUpgrader
from fuel_upgrade.engines.openstack import OpenStackUpgrader

from fuel_upgrade.before_upgrade_checker import CheckFreeSpace
from fuel_upgrade.before_upgrade_checker import CheckNoRunningTasks
from fuel_upgrade.before_upgrade_checker import CheckUpgradeVersions


#: A dict with supported systems.
#: The key is used for system option in CLI.
SUPPORTED_SYSTEMS = {
    'host-system': HostSystemUpgrader,
    'docker-init': DockerInitializer,
    'docker': DockerUpgrader,
    'bootstrap': BootstrapUpgrader,
    'openstack': OpenStackUpgrader,
}

#: A list of tuples of incompatible systems.
#: That's mean, if two of this systems has appered in user input
#: we gonna to show error that's impossible to do.
UNCOMPATIBLE_SYSTEMS = (
    ('docker-init', 'docker'),
)


def handle_exception(exc):
    logger.exception(exc)
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
        '--src', required=True, help='path to update file')
    parser.add_argument(
        '--no-checker', action='store_true',
        help='do not check before upgrade')
    parser.add_argument(
        '--no-rollback', action='store_true',
        help='do not rollback in case of errors')

    rv = parser.parse_args()

    # check input systems for compatibility
    for uncompatible_systems in UNCOMPATIBLE_SYSTEMS:
        if all(u_system in rv.systems for u_system in uncompatible_systems):
            parser.error(
                'the following systems are incompatible and can not be'
                'used at the same time: "{0}"'.format(
                    ', '.join(uncompatible_systems)
                )
            )

    return rv


def is_engine_in_list(engines_list, engine_class):
    """Checks if engine in the list

    :param list engines_list: list of engines
    :param engine_class: engine class

    :returns: True if engine in the list
              False if engine not in the list
    """
    engines = filter(
        lambda engine: isinstance(engine, engine_class),
        engines_list)
    if engines:
        return True

    return False


def run_upgrade(args):
    """Run upgrade on master node

    :param args: argparse object
    """
    # Initialize config
    config = build_config(args.src)
    logger.debug('Configuration data: {0}'.format(config))

    # Initialize upgrade engines
    upgraders_to_use = [
        SUPPORTED_SYSTEMS[system](config)
        for system in args.systems]

    # Initialize checkers
    checkers = None
    if not args.no_checker:
        checkers = [
            CheckFreeSpace(upgraders_to_use),
            CheckNoRunningTasks(config)]

        # NOTE(eli): Include version checker
        # only if docker upgrader is enabled
        if is_engine_in_list(upgraders_to_use, DockerUpgrader):
            checkers.append(CheckUpgradeVersions(config))

    # Initialize upgrade manager with engines and checkers
    upgrade_manager = UpgradeManager(
        upgraders_to_use, checkers, args.no_rollback)

    upgrade_manager.run()


def main():
    """Entry point
    """
    try:
        run_upgrade(parse_args())
    except Exception as exc:
        handle_exception(exc)
