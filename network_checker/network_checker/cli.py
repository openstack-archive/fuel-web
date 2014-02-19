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
"""Fuel network checker
Available verifications: multicast

Example:
  fuel-netcheck multicast serve listen send info clean

Multicast config options:
  group: 225.0.0.250
  port: 13310
  ttl: 5
  uid: '1001'
  repeat: 3
  iface: eth0
  timeout: 10

"""

import argparse
import json
import textwrap

from network_checker import api


def parse_args():
    parser = argparse.ArgumentParser(
        description=textwrap.dedent(__doc__),
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        'verification',
        help="Type of verification that should be started.")
    parser.add_argument(
        'actions', nargs='+',
        help="List of actions to perform.")
    #TODO(dshulyak) Add posibility to provide arguments like regular shell args
    parser.add_argument(
        '-c', '--config', default='{}',
        help="User defined configuration in json format.")
    return parser.parse_args()


def main():
    args = parse_args()
    user_data = json.loads(args.config)
    api_instance = api.Api(args.verification, **user_data)
    # Print only last response if user requires multiple sequantial actions
    for action in args.actions:
        result = getattr(api_instance, action)()
    print(json.dumps(result))
