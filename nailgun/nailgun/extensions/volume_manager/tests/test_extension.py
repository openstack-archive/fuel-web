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
from nailgun.test.base import BaseTestCase

from nailgun.extensions.volume_manager.extension import VolumeManagerExtension
from nailgun.extensions.volume_manager.objects.volumes import VolumeObject


@mock.patch.object(VolumeObject, 'delete_by_node_ids')
class TestExtension(BaseTestCase):

    def test_on_node_delete(self, obj_call_mock):
        node_mock = mock.MagicMock(id=1)
        VolumeManagerExtension.on_node_delete(node_mock)
        obj_call_mock.assert_called_once_with([1])

    def test_on_node_collection_delete(self, obj_call_mock):
        ids = [1, 2, 3]
        VolumeManagerExtension.on_node_collection_delete(ids)
        obj_call_mock.assert_called_once_with(ids)
