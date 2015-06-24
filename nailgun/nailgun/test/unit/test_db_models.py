# -*- coding: utf-8 -*-

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

from random import randint

from nailgun.db.sqlalchemy.models import Cluster
from nailgun.db.sqlalchemy.models import Release

from nailgun.test.base import BaseTestCase


class TestDbModels(BaseTestCase):

    def test_cluster_fuel_version_length(self):
        fuel_version = 'a' * 1024
        cluster_data = {
            'name': 'cluster-api-' + str(randint(0, 1000000)),
            'fuel_version': fuel_version,
            'release_id': self.env.create_release(api=False).id
        }

        cluster = Cluster(**cluster_data)
        self.db.add(cluster)
        self.db.commit()

    def test_release_environment_version(self):
        test_cases = (
            ('2014.1', '5.0'),
            ('2014.1-5.0', '5.0'),
            ('2014.1.1-5.0.1', '5.0.1'),
            ('2014.1.1-5.0.1-X', '5.0.1'),
            ('2014.1.1-5.1', '5.1'),
        )

        for version, enviroment_version in test_cases:
            self.assertEqual(
                Release(version=version).environment_version,
                enviroment_version)
