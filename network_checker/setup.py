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

import setuptools


setuptools.setup(
    name="nailgun-net-check",
    version='6.0.0',
    author="Mirantis Inc",
    classifiers=[
        "License :: OSI Approved :: Apache 2.0",
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Operating System :: POSIX",
        "Programming Language :: Python",
        "Topic :: Software Development :: Testing"
    ],
    include_package_data=True,
    packages=setuptools.find_packages(),
    entry_points={
        'console_scripts': [
            'net_probe.py = network_checker.net_check.api:main',
            'fuel-netcheck = network_checker.cli:main',
            'dhcpcheck = dhcp_checker.cli:main',
        ],
        'dhcp.check': [
            'discover = dhcp_checker.commands:ListDhcpServers',
            'request = dhcp_checker.commands:ListDhcpAssignment',
            'vlans = dhcp_checker.commands:DhcpWithVlansCheck'

        ],
        'network_checker': [
            'multicast = network_checker.multicast.api:MulticastChecker',
            'simple = network_checker.tests.simple:SimpleChecker'
        ]
    },
)
