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
import sys

from setuptools import find_packages
from setuptools import setup

name = 'nailgun'
version = '9.0.0'


def find_requires():
    dir_path = os.path.dirname(os.path.realpath(__file__))
    requirements = []
    with open('{0}/requirements.txt'.format(dir_path), 'r') as reqs:
        requirements = reqs.readlines()
    if sys.version_info == (2, 6):
        requirements.append('argparse')
        requirements.append('ordereddict')
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
    setup(
        name=name,
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
                ('nailgun_fixtures = '
                 'nailgun.db.sqlalchemy.fixman:upload_fixtures'),
                'nailgund = nailgun.app:appstart',
                'assassind = nailgun.assassin.assassind:run',
                'receiverd = nailgun.rpc.receiverd:run',
                'statsenderd = nailgun.statistics.statsenderd:run',
                'oswl_collectord = nailgun.statistics.oswl.collector:run',
                ('oswl_cleaner = nailgun.statistics.oswl.helpers:'
                 'delete_expired_oswl_entries'),
            ],
            'nailgun.extensions': [
                ('cluster_upgrade = nailgun.extensions.cluster_upgrade'
                 '.extension:ClusterUpgradeExtension'),
                ('volume_manager = nailgun.extensions.volume_manager'
                 '.extension:VolumeManagerExtension')
            ],
        },
        data_files=recursive_data_files([('share/nailgun', 'static')]),
    )
