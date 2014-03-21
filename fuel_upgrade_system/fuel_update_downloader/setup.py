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
import os.path

from setuptools import find_packages
from setuptools import setup


def find_requires():
    dir_path = os.path.dirname(os.path.realpath(__file__))
    requirements = []
    with open('{0}/requirements.txt'.format(dir_path), 'r') as reqs:
        requirements = reqs.readlines()
    return requirements


if __name__ == "__main__":
    setup(name='fuel_update_downloader',
          version='0.1.0',
          description='Updates downloader for Fuel-master node',
          long_description="""Updates downloader for Fuel-master node""",
          classifiers=[
              "Programming Language :: Python",
              "Topic :: System :: Software Distribution"],
          author='Mirantis Inc.',
          author_email='product@mirantis.com',
          url='http://mirantis.com',
          keywords='fuel download upgrade mirantis',
          packages=find_packages(),
          zip_safe=False,
          install_requires=find_requires(),
          include_package_data=True,
          entry_points={
              'console_scripts': [
                  'fuel-update-downloader = fuel_update_downloader.cli:main']})
