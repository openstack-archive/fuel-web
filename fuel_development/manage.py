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
import os
import sys

from fabric.api import env
from fabric.colors import red
from fabric.context_managers import hide
from fabric.context_managers import settings


def load_nailgun_deploy_parser(operation_parser):
    deploy_parser = operation_parser.add_parser('deploy')

    cur_dir = os.path.dirname(__file__)
    default_dir = os.path.realpath(os.path.join(cur_dir, '..'))
    deploy_parser.add_argument(
        '-d', '--fuelweb-dir',
        type=str,
        help="Path to fuel-web repository "
             "(if not set '{0}' will be used)".format(default_dir),
        default=default_dir
    )
    deploy_parser.add_argument(
        '--synconly',
        action='store_true',
        help="Synchronize source and restart service "
             "without masternode configuration"
    )


def load_nailgun_revert_parser(operation_parser):
    operation_parser.add_parser('revert')


def load_nailgun_parser(subparsers):
    nailgun_parser = subparsers.add_parser(
        'nailgun', help="Processing nailgun operations"
    )
    operation_parser = nailgun_parser.add_subparsers(
        dest='command',
        help="Deploy or revert nailgun development environment on masternode"
    )
    load_nailgun_deploy_parser(operation_parser)
    load_nailgun_revert_parser(operation_parser)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    default_masternode_addr = '10.20.0.2'
    parser.add_argument(
        '-m', '--masternode-addr',
        help="Master node address ('{0}' by default)".format(
            default_masternode_addr
        ),
        default=default_masternode_addr
    )

    subparsers = parser.add_subparsers(
        dest='action',
        help="Targets to be developed on master node"
    )

    load_nailgun_parser(subparsers)
    params = parser.parse_args()

    # Configuring fabric global params
    env.host_string = params.masternode_addr
    env.user = 'root'

    # Loading configurator by action value
    action_module = __import__('configurator.{0}'.format(params.action))
    processor = getattr(action_module, params.action)

    # Executing action
    try:
        with settings(hide('running', 'stdout')):
            processor.action(params)
    except Exception as e:
        print(red("Configuration failed: {0}".format(e)))
        # Exiting with general error code
        sys.exit(1)
