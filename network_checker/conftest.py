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

import os


PIDFILE = '/tmp/vde_network_checker'
IFACES = ['tap11', 'tap12']


def pytest_addoption(parser):
    parser.addoption("--vde", action='store_true', default=False,
                     help="Use vde switch for network verification.")


def pytest_configure(config):
    if config.getoption('vde'):
        base = 'vde_switch -p {pidfile} -d'.format(pidfile=PIDFILE)
        command = [base]
        taps = ['-tap {tap}'.format(tap=tap) for tap in IFACES]
        full_command = command + taps
        os.system(' '.join(full_command))
        for tap in IFACES:
            os.system('ifconfig {tap} up'.format(tap=tap))
        os.environ['NET_CHECK_IFACE_1'] = IFACES[0]
        os.environ['NET_CHECK_IFACE_2'] = IFACES[1]


def pytest_unconfigure(config):
    if os.path.exists(PIDFILE):
        with open(PIDFILE) as f:
            pid = f.read().strip()
            os.kill(int(pid), 15)
