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

import setuptools

requires = [
    'argparse',
    'daemonize',
    'pyyaml'
]

major_version = '0.1'
minor_version = '0'
name = 'tasklib'

version = "%s.%s" % (major_version, minor_version)


setuptools.setup(
    name=name,
    version=version,
    description='Tasklib package',
    long_description="""Tasklib is intended to be medium between different
    configuration management solutions and orchestrator.
    This is required to support plugable tasks/actions with good
    amount of control, such as stop/pause/poll state.
    """,
    classifiers=[
        "Development Status :: 4 - Beta",
        "Programming Language :: Python",
    ],
    author='Mirantis Inc.',
    author_email='product@mirantis.com',
    url='http://mirantis.com',
    keywords='tasklib mirantis',
    packages=setuptools.find_packages(),
    zip_safe=False,
    install_requires=requires,
    include_package_data=True,
    entry_points={
        'console_scripts': [
            'taskcmd = tasklib.cli:main',
        ]})
