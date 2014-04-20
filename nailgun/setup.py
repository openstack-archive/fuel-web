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

import os
import os.path

from setuptools import find_packages
from setuptools import setup

major_version = '0.1'
minor_version = '0'
name = 'nailgun'

version = "%s.%s" % (major_version, minor_version)


def find_requires():
    dir_path = os.path.dirname(os.path.realpath(__file__))
    requirements = []
    with open('{0}/requirements.txt'.format(dir_path), 'r') as reqs:
        requirements = reqs.readlines()
    return requirements


def recursive_data_files(spec_data_files):
    result = []
    for dstdir, srcdir in spec_data_files:
        for topdir, dirs, files in os.walk(srcdir):
            for f in files:
                result.append((os.path.join(dstdir, topdir),
                               [os.path.join(topdir, f)]))
    return result


if __name__ == "__main__":
    setup(name=name,
          version=version,
          description='Nailgun package',
          long_description="""Nailgun package""",
          classifiers=[
              "Development Status :: 4 - Beta",
              "Programming Language :: Python",
              "Topic :: Internet :: WWW/HTTP",
              "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
          ],
          author='Mirantis Inc.',
          author_email='product@mirantis.com',
          url='http://mirantis.com',
          keywords='web wsgi nailgun mirantis',
          packages=find_packages(),
          zip_safe=False,
          install_requires=find_requires(),
          include_package_data=True,
          scripts=['manage.py'],
          entry_points={
              'console_scripts': [
                  'nailgun_syncdb = nailgun.db:syncdb',
                  'nailgun_fixtures = \
                      nailgun.db.sqlalchemy.fixman:upload_fixtures',
                  'nailgund = nailgun.app:appstart',
                  'assassind = nailgun.assassin.assassind:run',
                  'receiverd = nailgun.rpc.receiverd:run'
              ],
              'nose.plugins.0.10': [
                  'db = nailgun.test.db_plugin:DbPlugin'
              ]
          },
          data_files=recursive_data_files([('share/nailgun', 'static')])
          )
