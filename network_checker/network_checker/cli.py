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
<check> should be multicast | dhcp | l2
<command> should be listen | send | get_info
<config> arbitrary set of jsonized parameters specific for each check

Usage:
  fuel-netcheck <check> <command> <config>
  fuel-netcheck (-h | --help)
  fuel-netcheck --version

Examples:
  fuel-netcheck multicast listen '{"node_id": "111", "group": "225.0.0.250",
  "port": 8890}'
  fuel-netcheck multicast send '{"node_id": "111", "group": "225.0.0.250",
  "port": 8890}'
  fuel-netcheck multicast get_info '{"node_id": "111", "group": "225.0.0.250",
  "port": 8890}'

Options:
  -h --help     Show this screen.
  --version     Show version.

"""

import json
import sys

from docopt import docopt

from network_checker import api


def main():
    # cli is very usefull for debugging purposes
    arguments = docopt(__doc__, version='Fuel Network Checker 0.1')
    config = json.loads(arguments['<config>'])
    api_instance = api.Api(arguments['<check>'], config)
    result = getattr(api_instance, arguments['<command>'])()
    print(result)
    sys.exit(0)
