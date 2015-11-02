# -*- coding: utf-8 -*-

#    Copyright 2015 Mirantis, Inc.
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

import mock
from nailgun import consts
from nailgun.test.base import BaseTestCase

from ..extension import VolumeManagerExtension
from ..objects.volumes import VolumeObject


class TestExtension(BaseTestCase):

    @mock.patch.object(VolumeObject, 'delete_by_node_ids')
    def test_on_node_delete(self, obj_call_mock):
        node_mock = mock.MagicMock(id=1)
        VolumeManagerExtension.on_node_delete(node_mock)
        obj_call_mock.assert_called_once_with([1])

    @mock.patch.object(VolumeObject, 'delete_by_node_ids')
    def test_on_node_collection_delete(self, obj_call_mock):
        ids = [1, 2, 3]
        VolumeManagerExtension.on_node_collection_delete(ids)
        obj_call_mock.assert_called_once_with(ids)

    @mock.patch.object(VolumeManagerExtension, 'set_default_node_volumes')
    def test_on_node_update(self, mock_set_default_node_volumes):
        ext = VolumeManagerExtension()
        should_reset_env_statuses = set([consts.NODE_STATUSES.discover])
        should_not_reset_env_statuses = \
            set(consts.NODE_STATUSES) - should_reset_env_statuses

        for status in should_reset_env_statuses:
            node = mock.MagicMock(status=status)
            mock_set_default_node_volumes.reset_mock()
            ext.on_node_update(node)
            ext.set_default_node_volumes.assert_called_once_with(node)

        for status in should_not_reset_env_statuses:
            node = mock.MagicMock(status=status)
            mock_set_default_node_volumes.reset_mock()
            ext.on_node_update(node)
            self.assertFalse(ext.set_default_node_volumes.called)
