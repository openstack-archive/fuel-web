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
import re

from setuptools import find_packages
from setuptools import setup


def parse_requirements_txt():
    """Parses requirements.txt and returns arrays with `install_requires`
    packages and with `dependency_links` sources.
    """
    root = os.path.dirname(os.path.abspath(__file__))

    requirements = []
    dependencies = []

    with open(os.path.join(root, 'requirements.txt'), 'r') as f:
        for line in f.readlines():
            line = line.rstrip()
            if not line or line.startswith('#'):
                continue

            egg = re.match('git\+.*#egg=(.*)$', line)
            if egg is not None:
                egg = egg.groups()[0]
                requirements.append(egg)
                dependencies.append(line)
            else:
                requirements.append(line)

    return requirements, dependencies
REQUIREMENTS, DEPENDENCIES = parse_requirements_txt()


setup(
    name='fuel_upgrade',
    version='0.1.0',
    description='Upgrade system for Fuel-master node',
    long_description="""Upgrade system for Fuel-master node""",
    classifiers=[
        "Programming Language :: Python",
        "Topic :: System :: Software Distribution"],
    author='Mirantis Inc.',
    author_email='product@mirantis.com',
    url='http://mirantis.com',
    keywords='fuel upgrade mirantis',
    packages=find_packages(),
    zip_safe=False,
    install_requires=REQUIREMENTS,
    dependency_links=DEPENDENCIES,
    include_package_data=True,
    package_data={'': ['*.yaml', 'templates/*']},
    entry_points={
        'console_scripts': [
            'fuel-upgrade = fuel_upgrade.cli:main']})
