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
import signal
import sys

import yaml

from fuel_agent_ci import manager as ci_manager

logging.basicConfig(level=logging.DEBUG)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-f', '--file', dest='env_file', action='store',
        type=str, help='Environment data file', required=True
    )

    subparsers = parser.add_subparsers(dest='action')

    env_parser = subparsers.add_parser('env')
    env_parser.add_argument(
        '-a', '--action', dest='env_action', action='store',
        type=str, help='Env action', required=True
    )
    env_parser.add_argument(
        '-k', '--kwargs', dest='env_kwargs', action='store',
        type=str, required=False,
        help='Env action kwargs, must be valid json or yaml',
    )
    env_parser.add_argument(
        '-K', '--kwargs_file', dest='env_kwargs_file', action='store',
        type=str, required=False,
        help='Env action kwargs file, content must be valid json or yaml',
    )

    item_parser = subparsers.add_parser('item')
    item_parser.add_argument(
        '-t', '--type', dest='item_type', action='store',
        type=str, help='Item type', required=True
    )
    item_parser.add_argument(
        '-a', '--action', dest='item_action', action='store',
        type=str, help='Item action', required=True
    )
    item_parser.add_argument(
        '-n', '--name', dest='item_name', action='store',
        type=str, help='Item name', required=False
    )
    item_parser.add_argument(
        '-k', '--kwargs', dest='item_kwargs', action='store',
        type=str, required=False,
        help='Item action kwargs, must be valid json or yaml',
    )
    item_parser.add_argument(
        '-K', '--kwargs_file', dest='item_kwargs_file', action='store',
        type=str, required=False,
        help='Item action kwargs file, content must be valid json or yaml',
    )

    return parser


def main():
    def term_handler(signum=None, sigframe=None):
        sys.exit()
    signal.signal(signal.SIGTERM, term_handler)
    signal.signal(signal.SIGINT, term_handler)

    parser = parse_args()
    params, other_params = parser.parse_known_args()
    with open(params.env_file) as f:
        env_data = yaml.load(f.read())

    manager = ci_manager.Manager(env_data)
    # print 'params: %s' % params
    # print 'other_params: %s' % other_params

    if params.action == 'env':
        kwargs = {}
        if params.env_kwargs:
            kwargs.update(yaml.load(params.env_kwargs))
        elif params.env_kwargs_file:
            with open(params.env_kwargs_file) as f:
                kwargs.update(yaml.load(f.read()))
        manager.do_env(params.env_action, **kwargs)
    elif params.action == 'item':
        kwargs = {}
        if params.item_kwargs:
            kwargs.update(yaml.load(params.item_kwargs))
        elif params.item_kwargs_file:
            with open(params.item_kwargs_file) as f:
                kwargs.update(yaml.load(f.read()))
        manager.do_item(params.item_type, params.item_action,
                        params.item_name, **kwargs)


if __name__ == '__main__':
    main()
