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

import argparse
import logging

import yaml

from fuel_agent_ci import manager as ci_manager

logging.basicConfig(level=logging.DEBUG)


def parse_args():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='action')

    create_parser = subparsers.add_parser('create')
    create_parser.add_argument(
        '-f', '--file', dest='env_file', action='store',
        type=str, help='Environment data file', required=True
    )

    destroy_parser = subparsers.add_parser('destroy')
    destroy_parser.add_argument(
        '-f', '--file', dest='env_file', action='store',
        type=str, help='Environment data file', required=True
    )
    return parser


def main():
    parser = parse_args()
    params, other_params = parser.parse_known_args()
    with open(params.env_file, "r") as f:
        env_data = yaml.load(f.read())

    manager = ci_manager.Manager(env_data)
    if params.action == 'create':
        manager.define()
    elif params.action == 'destroy':
        manager.undefine()


if __name__ == '__main__':
    main()
