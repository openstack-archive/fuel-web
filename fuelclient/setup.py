#!/usr/bin/env python
#    Copyright 2013 Mirantis, Inc.
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

from setuptools import setup

setup(
    name='python-fuelclient',
    version='0.1',
    description='Command line interface for Nailgun',
    long_description="""Command line interface for Nailgun""",
    author='Mirantis Inc.',
    author_email='product@mirantis.com',
    url='http://mirantis.com',
    install_requires=['PyYAML==3.10'],
    scripts=['fuel']
)
