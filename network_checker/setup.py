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
    version='0.1',
    author="Mirantis Inc",
    classifiers=[
        "License :: OSI Approved :: Apache 2.0",
        "Development Status :: 5 - Production/Stable",
        "Environment :: Console",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: POSIX",
        "Programming Language :: Python",
        "Topic :: Software Development :: Testing"
    ],
    install_requires=[
        'argparse'
    ],
    include_package_data=True,
    packages=['net_check'],
    entry_points={
        'console_scripts': [
            'net_probe.py = net_check.api:main'
        ],
    },
)
