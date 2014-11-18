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
import getpass
import logging
import requests
import sys

from fuel_upgrade.logger import configure_logger

from fuel_upgrade import errors
from fuel_upgrade import messages

from fuel_upgrade.checker_manager import CheckerManager
from fuel_upgrade.config import build_config
from fuel_upgrade.upgrade import UpgradeManager

from fuel_upgrade.engines.bootstrap import BootstrapUpgrader
from fuel_upgrade.engines.docker_engine import DockerInitializer
from fuel_upgrade.engines.docker_engine import DockerUpgrader
from fuel_upgrade.engines.host_system import HostSystemUpgrader
from fuel_upgrade.engines.openstack import OpenStackUpgrader
from fuel_upgrade.engines.targetimages import TargetImagesUpgrader

from fuel_upgrade.pre_upgrade_hooks import PreUpgradeHookManager


logger = logging.getLogger(__name__)

#: A dict with supported systems.
#: The key is used for system option in CLI.
SUPPORTED_SYSTEMS = {
    'host-system': HostSystemUpgrader,
    'docker-init': DockerInitializer,
    'docker': DockerUpgrader,
    'bootstrap': BootstrapUpgrader,
    'openstack': OpenStackUpgrader,
    'targetimages': TargetImagesUpgrader
}

#: A list of tuples of incompatible systems.
#: That's mean, if two of this systems has appered in user input
#: we gonna to show error that's impossible to do.
UNCOMPATIBLE_SYSTEMS = (
    ('docker-init', 'docker'),
)


def handle_exception(exc):
    logger.exception('%s', exc)

    print(messages.header)

    # TODO(ikalnitsky): use some kind of map instead of condition stairs
    if isinstance(exc, requests.ConnectionError):
        print(messages.docker_is_dead)
    elif isinstance(exc, errors.UpgradeVerificationError):
        print(messages.health_checker_failed)
    elif isinstance(exc, errors.NailgunIsNotRunningError):
        print(messages.nailgun_is_not_running)
    elif isinstance(exc, errors.OstfIsNotRunningError):
        print(messages.ostf_is_not_running)
    elif isinstance(exc, errors.CommandError):
        print(exc)

    sys.exit(-1)


def parse_args(args):
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
    parser.add_argument(
        '--password', help="admin user password")

    rv = parser.parse_args(args)

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
    # Get admin password
    if not args.password:
        args.password = getpass.getpass('Admin Password: ')

    # recheck pasword again
    if not args.password:
        raise errors.CommandError(messages.no_password_provided)

    # Initialize config
    config = build_config(args.src, args.password)
    logger.debug('Configuration data: %s', config)

    # Initialize upgrade engines
    upgraders_to_use = [
        SUPPORTED_SYSTEMS[system](config)
        for system in args.systems]

    # Initialize checkers
    if not args.no_checker:
        checker_manager = CheckerManager(upgraders_to_use, config)
        checker_manager.check()

    # Initialize pre upgrade hook manager
    hook_manager = PreUpgradeHookManager(upgraders_to_use, config)
    hook_manager.run()

    # Initialize upgrade manager with engines and checkers
    upgrade_manager = UpgradeManager(upgraders_to_use, args.no_rollback)
    upgrade_manager.run()


def main():
    """Entry point
    """
    configure_logger('/var/log/fuel_upgrade.log')
    try:
        run_upgrade(parse_args(sys.argv[1:]))
    except Exception as exc:
        handle_exception(exc)
