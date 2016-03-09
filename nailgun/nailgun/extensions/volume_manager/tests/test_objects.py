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

from nailgun.test.base import BaseTestCase

from nailgun.extensions.volume_manager.models.node_volumes import NodeVolumes
from nailgun.extensions.volume_manager.objects.volumes import VolumeObject


class TestExtension(BaseTestCase):

    def test_delete_by_node_ids(self):
        volumes = [
            {'node_id': 1, 'volumes': 'volume_1'},
            {'node_id': 2, 'volumes': 'volume_2'},
            {'node_id': 3, 'volumes': 'volume_3'}]
        for volume in volumes:
            self.db.add(NodeVolumes(**volume))
        self.db.commit()
        self.assertEqual(self.db.query(NodeVolumes).count(), 3)
        VolumeObject.delete_by_node_ids([1, 2])
        self.assertEqual(self.db.query(NodeVolumes).count(), 1)

        volume = self.db.query(NodeVolumes).first()
        self.assertEqual(volume.node_id, 3)
        self.assertEqual(volume.volumes, 'volume_3')
