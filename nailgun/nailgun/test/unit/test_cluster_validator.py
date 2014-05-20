# -*- coding: utf-8 -*-
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

from contextlib import nested

from mock import Mock
from mock import patch

from nailgun.api.v1.validators.cluster import ClusterValidator
from nailgun.errors import errors
from nailgun.test.base import BaseTestCase


class TestClusterValidator(BaseTestCase):
    def setUp(self):
        super(TestClusterValidator, self).setUp()
        self.cluster_data = '{"name": "test", "release": 1}'

    def test_cluster_exists_validation(self):
        with patch(
            'nailgun.api.v1.validators.cluster.ClusterCollection',
            Mock()
        ) as cc:
            cc.filter_by.return_value.first.return_value = 'cluster'
            self.assertRaises(errors.AlreadyExists,
                              ClusterValidator.validate, self.cluster_data)

    def test_cluster_non_exists_validation(self):
        with nested(
            patch(
                'nailgun.api.v1.validators.cluster.ClusterCollection',
                Mock()
            ),
            patch('nailgun.api.v1.validators.cluster.Release', Mock())
        ) as (cc, r):
            try:
                cc.filter_by.return_value.first.return_value = None
                r.get_by_uuid.return_value = 'release'
                ClusterValidator.validate(self.cluster_data)
            except errors.AlreadyExists as e:
                self.fail(
                    'Cluster exists validation failed: {0}'.format(e)
                )

    def test_release_exists_validation(self):
        with patch(
            'nailgun.api.v1.validators.cluster.ClusterCollection',
            Mock()
        ) as cc:
            cc.filter_by.return_value.first.return_value = None
            self.assertRaises(errors.InvalidData,
                              ClusterValidator.validate, self.cluster_data)

    def test_release_non_exists_validation(self):
        with patch('nailgun.api.v1.validators.cluster.Release', Mock()) as r:
            try:
                r.get_by_uuid.return_value = None
                ClusterValidator.validate(self.cluster_data)
            except errors.InvalidData as e:
                self.fail('Release exists validation failed: {0}'.format(e))
