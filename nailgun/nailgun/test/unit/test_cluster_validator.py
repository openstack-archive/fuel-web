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

from mock import Mock
from mock import patch
from mock import PropertyMock
from oslo_serialization import jsonutils

from nailgun.api.v1.validators.cluster import ClusterStopDeploymentValidator
from nailgun.api.v1.validators.cluster import ClusterValidator
from nailgun import consts
from nailgun.errors import errors
from nailgun import objects
from nailgun.test.base import BaseTestCase


class TestClusterValidator(BaseTestCase):
    @classmethod
    def setUpClass(cls):
        super(TestClusterValidator, cls).setUpClass()
        cls.cluster_data = jsonutils.dumps({
            "name": "test",
            "release": 1,
            "mode": consts.CLUSTER_MODES.ha_compact})

    @patch('nailgun.api.v1.validators.cluster.objects'
           '.ClusterCollection.filter_by')
    @patch('nailgun.api.v1.validators.cluster.objects.Release.get_by_uid')
    def test_cluster_exists_validation(self, release_get_by_uid, cc_filter_by):
        release_get_by_uid.return_value = Mock(modes=[
            consts.CLUSTER_MODES.ha_compact])
        cc_filter_by.return_value.first.return_value = 'cluster'
        self.assertRaises(errors.AlreadyExists,
                          ClusterValidator.validate, self.cluster_data)

    @patch('nailgun.api.v1.validators.cluster.objects'
           '.ClusterCollection.filter_by')
    @patch('nailgun.api.v1.validators.cluster.objects.Release.get_by_uid')
    def test_cluster_does_not_exist_validation(self, release_get_by_uid,
                                               cc_filter_by):
        try:
            cc_filter_by.return_value.first.return_value = None
            release_get_by_uid.return_value = Mock(modes=[
                consts.CLUSTER_MODES.ha_compact])
            ClusterValidator.validate(self.cluster_data)
        except errors.AlreadyExists as e:
            self.fail(
                'Cluster exists validation failed: {0}'.format(e)
            )

    @patch('nailgun.api.v1.validators.cluster.objects'
           '.ClusterCollection.filter_by')
    def test_release_exists_validation(self, cc_filter_by):
        cc_filter_by.return_value.first.return_value = None
        self.assertRaises(errors.InvalidData,
                          ClusterValidator.validate, self.cluster_data)

    @patch('nailgun.api.v1.validators.cluster.objects.Release.get_by_uid')
    def test_release_non_exists_validation(self, release_get_by_uid):
        release_get_by_uid.return_value = None
        self.assertRaises(errors.InvalidData,
                          ClusterValidator.validate, self.cluster_data)

    @patch('nailgun.api.v1.validators.cluster.objects.Release.get_by_uid')
    def test_release_unavailable_validation(self, release_get_by_uid):
        type(release_get_by_uid.return_value).state = PropertyMock(
            return_value=consts.RELEASE_STATES.unavailable)
        self.assertRaises(errors.NotAllowed,
                          ClusterValidator.validate, self.cluster_data)

    def test_pending_release_validation_success(self):
        curr_release = Mock(
            id=1,
            operating_system='Ubuntu',
            version='2014.1',
            can_update_from_versions=[],
        )
        pend_release = Mock(
            id=2,
            operating_system='Ubuntu',
            version='2014.2',
            can_update_from_versions=['2014.1'],
        )

        self.assertTrue(
            ClusterValidator._can_update_release(
                curr_release, curr_release
            )
        )

        self.assertTrue(
            ClusterValidator._can_update_release(
                curr_release, pend_release
            )
        )

        self.assertTrue(
            ClusterValidator._can_update_release(
                pend_release, curr_release
            )
        )

    def test_pending_release_validation_unsuccess(self):
        curr_release = Mock(
            id=1,
            operating_system='Ubuntu',
            version='2014.1',
            can_update_from_versions=[],
        )
        pend_release = Mock(
            id=2,
            operating_system='Ubuntu',
            version='2014.2',
            can_update_from_versions=[],
        )
        self.assertFalse(
            ClusterValidator._can_update_release(
                curr_release, pend_release
            )
        )

        pend_release = Mock(
            id=2,
            operating_system='CentOS',
            version='2014.2',
            can_update_from_versions=['2014.1'],
        )
        self.assertFalse(
            ClusterValidator._can_update_release(
                curr_release, pend_release
            )
        )

        curr_release = Mock(
            id=1,
            operating_system='Ubuntu',
            version='2014.1',
            can_update_from_versions=[],
        )
        pend_release = Mock(
            id=2,
            operating_system='Ubuntu',
            version='2014.2',
            can_update_from_versions=['2014.0'],
        )
        self.assertFalse(
            ClusterValidator._can_update_release(
                pend_release, curr_release
            )
        )

    @patch('nailgun.api.v1.validators.cluster.objects'
           '.ClusterCollection.filter_by')
    @patch('nailgun.api.v1.validators.cluster.objects.Release.get_by_uid')
    def test_mode_check_passes(self, release_get_by_uid, cc_filter_by):
        release_get_by_uid.return_value = Mock(modes=[
            consts.CLUSTER_MODES.ha_compact])

        cc_filter_by.return_value.first.return_value = None
        try:
            ClusterValidator.validate(self.cluster_data)
        except errors.InvalidData as e:
            self.fail('test_mode_check failed: {0}'.format(e))

    @patch('nailgun.api.v1.validators.cluster.objects'
           '.ClusterCollection.filter_by')
    @patch('nailgun.api.v1.validators.cluster.objects.Release.get_by_uid')
    def test_mode_check_fails(self, release_get_by_uid, cc_filter_by):
        release_get_by_uid.return_value = Mock(
            modes=['trolomod', 'multinode'])

        cc_filter_by.return_value.first.return_value = None
        self.assertRaisesRegexp(errors.InvalidData,
                                "Cannot deploy in .* mode in current release",
                                ClusterValidator.validate,
                                self.cluster_data)

    @patch('nailgun.api.v1.validators.cluster.objects'
           '.ClusterCollection.filter_by')
    @patch('nailgun.api.v1.validators.cluster.objects.Release.get_by_uid')
    def test_update_mode_check_passes(self, release_get_by_uid, cc_filter_by):
        release_mock = Mock(
            modes=[consts.CLUSTER_MODES.ha_compact, 'multinode'])
        release_get_by_uid.return_value = release_mock

        cluster_mock = Mock(id=1, release_id=1, release=release_mock)
        cc_filter_by.return_value.first.return_value = None
        try:
            ClusterValidator.validate_update(self.cluster_data, cluster_mock)
        except errors.InvalidData as e:
            self.fail('test_mode_check failed: {0}'.format(e))

    @patch('nailgun.api.v1.validators.cluster.objects'
           '.ClusterCollection.filter_by')
    @patch('nailgun.api.v1.validators.cluster.objects.Release.get_by_uid')
    def test_update_mode_check_fails(self, release_get_by_uid, cc_filter_by):
        release_mock = Mock(
            modes=['trolomod', 'multinode'])

        cluster_mock = Mock(id=1, release_id=1, release=release_mock)
        cc_filter_by.return_value.first.return_value = None
        self.assertRaisesRegexp(errors.InvalidData,
                                "Cannot deploy in .* mode in current release",
                                ClusterValidator.validate_update,
                                self.cluster_data,
                                cluster_mock)


class TestClusterStopDeploymentValidator(BaseTestCase):

    # FIXME(aroma): remove this test when stop action will be reworked for ha
    # cluster. To get more details, please, refer to [1]
    # [1]: https://bugs.launchpad.net/fuel/+bug/1529691
    def test_stop_deployment_failed_for_once_deployed_cluster(self):
        cluster = self.env.create_cluster(api=False)

        objects.Cluster.flip_deployed_before_flag(cluster, value=True)

        self.assertRaises(
            errors.CannotBeStopped,
            ClusterStopDeploymentValidator.validate,
            cluster
        )
