# -*- coding: utf-8 -*-

#    Copyright 2016 Mirantis, Inc.
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
from nailgun.orchestrator.stages import stage_serialize
from nailgun.test import base


class TestStages(base.BaseUnitTest):
    @patch('nailgun.orchestrator.priority_serializers.PriorityStrategy.'
           'one_by_one')
    def test_stage_serialize(self, m_one_by_one):
        standard = ['first', 'middle', 'last']
        serializer = Mock()
        serializer.serialize_begin_tasks = Mock(return_value=[standard[0]])
        serializer.serialize_end_tasks = Mock(return_value=[standard[2]])
        graph_tasks = [standard[1]]

        self.assertItemsEqual(stage_serialize(serializer, graph_tasks),
                              standard)
        m_one_by_one.assert_called_once_with(standard)
