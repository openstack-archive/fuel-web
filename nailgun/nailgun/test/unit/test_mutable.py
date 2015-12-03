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

from copy import copy
from copy import deepcopy
from mock import patch

from nailgun.db.sqlalchemy.models.mutable import MutableList
from nailgun.test.base import BaseUnitTest


def patch_method_changed():
    return patch('nailgun.db.sqlalchemy.models.mutable.MutableList.changed')


def patch_method_coerce():
    return patch('sqlalchemy.ext.mutable.Mutable.coerce')


class TestMutableList(BaseUnitTest):
    def setUp(self):
        self.m_list = MutableList()

    @patch_method_coerce()
    def test_coerce_mutable_list(self, m_coerce):
        lst = MutableList()
        self.assertIsInstance(self.m_list.coerce('key', lst), MutableList)
        m_coerce.assert_not_called()

    @patch_method_coerce()
    def test_coerce_list(self, m_coerce):
        lst = list()
        self.assertIsInstance(self.m_list.coerce('key', lst), MutableList)
        m_coerce.assert_not_called()

    @patch_method_coerce()
    def test_coerce_not_acceptable_object(self, m_coerce):
        m_coerce.return_value = None
        obj = dict()
        self.m_list.coerce('key', obj)
        m_coerce.assert_called_once_with('key', obj)

    @patch_method_changed()
    def test_append(self, m_changed):
        self.m_list.append('element')
        self.assertEqual(['element'], self.m_list)
        m_changed.assert_called_once_with()

    @patch_method_changed()
    def test_extend(self, m_changed):
        self.m_list.extend(('element1', 'element2', 'element3'))
        self.assertEqual(
            self.m_list,
            ['element1', 'element2', 'element3'])
        m_changed.assert_called_once_with()

    @patch_method_changed()
    def test_extend_failure(self, m_changed):
        self.assertRaises(TypeError, self.m_list.extend, None)
        self.assertEqual([], self.m_list)
        m_changed.assert_not_called()

    def test_insert(self):
        self.m_list.extend(('element1', 'element2'))
        with patch_method_changed() as m_changed:
            self.m_list.insert(1, 'new_element')
            self.assertEqual(
                self.m_list,
                ['element1', 'new_element', 'element2'])
            m_changed.assert_called_once_with()

    @patch_method_changed()
    def test_insert_failure(self, m_changed):
        self.assertRaises(TypeError, self.m_list.insert, None, 'element')
        self.assertEqual([], self.m_list)
        m_changed.assert_not_called()

    def test_pop_default(self):
        self.m_list.extend(('element1', 'element2'))
        with patch_method_changed() as m_changed:
            self.assertEqual('element2', self.m_list.pop())
            self.assertEqual(['element1'], self.m_list)
            m_changed.assert_called_once_with()

    @patch_method_changed()
    def test_pop_default_from_empty_list(self, m_changed):
        self.assertRaises(IndexError, self.m_list.pop)
        self.assertEqual([], self.m_list)
        m_changed.assert_not_called()

    def test_pop_of_specified_element(self):
        self.m_list.extend(('element1', 'element2'))
        with patch_method_changed() as m_changed:
            self.assertEqual('element1', self.m_list.pop(0))
            self.assertEqual(['element2'], self.m_list)
            m_changed.assert_called_once_with()

    def test_pop_wrong_index_type(self):
        self.m_list.extend(('element1', 'element2'))
        with patch_method_changed() as m_changed:
            self.assertRaises(TypeError, self.m_list.pop, 'str')
            self.assertEqual(['element1', 'element2'], self.m_list)
            m_changed.assert_not_called()

    def test_pop_out_of_range(self):
        self.m_list.extend(('element1', 'element2'))
        with patch_method_changed() as m_changed:
            self.assertRaises(IndexError, self.m_list.pop, 2)
            self.assertEqual(['element1', 'element2'], self.m_list)
            m_changed.assert_not_called()

    def test_remove(self):
        self.m_list.extend(('element1', 'element2', 'element1'))
        with patch_method_changed() as m_changed:
            self.m_list.remove('element1')
            self.assertEqual(['element2', 'element1'], self.m_list)
            m_changed.assert_called_once_with()

    @patch_method_changed()
    def test_remove_failure(self, m_changed):
        self.assertRaises(ValueError, self.m_list.remove, None)
        m_changed.assert_not_called()

    def test_set_item(self):
        self.m_list.extend(('element1', 'element2'))
        with patch_method_changed() as m_changed:
            self.m_list[0] = 'new_element'
            self.assertEqual(['new_element', 'element2'], self.m_list)
            m_changed.assert_called_once_with()

    @patch_method_changed()
    def test_set_item_failure(self, m_changed):
        self.assertRaises(IndexError, self.m_list.__setitem__, 0, 'element')
        m_changed.assert_not_called()

    def test_del_item(self):
        self.m_list.extend(('element1', 'element2'))
        with patch_method_changed() as m_changed:
            del self.m_list[0]
            self.assertEqual(['element2'], self.m_list)
            m_changed.assert_called_once_with()

    @patch_method_changed()
    def test_del_item_failure(self, m_changed):
        self.assertRaises(IndexError, self.m_list.__delitem__, 0)
        m_changed.assert_not_called()

    @patch_method_changed()
    def test_get_state(self, m_changed):
        self.assertIsInstance(self.m_list.__getstate__(), list)
        m_changed.assert_not_called()

    @patch_method_changed()
    def test_set_state(self, m_changed):
        self.m_list.__setstate__(['element1', 'element2'])
        self.assertEqual(['element1', 'element2'], self.m_list)
        m_changed.assert_called_once_with()

    @patch_method_changed()
    def test_set_state_failure(self, m_changed):
        self.assertRaises(TypeError, self.m_list.__setstate__, None)
        m_changed.assert_not_called()

    def test_copy(self):
        self.m_list.extend(('element1', 'element2'))
        clone = copy(self.m_list)
        self.assertEqual(clone, self.m_list)

    def test_deep_copy(self):
        lst = MutableList(('element1', 'element2'))
        self.m_list.extend((lst, 'element3'))
        clone = deepcopy(self.m_list)
        lst[0] = 'new_element'
        self.assertEqual(clone[0][0], 'element1')
