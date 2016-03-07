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
from mock import Mock
from mock import patch

from nailgun.db.sqlalchemy.models.mutable import MutableDict
from nailgun.db.sqlalchemy.models.mutable import MutableList
from nailgun.test.base import BaseUnitTest


@patch('sqlalchemy.ext.mutable.Mutable.coerce')
class TestMutableDictCoerce(BaseUnitTest):
    def setUp(self):
        super(TestMutableDictCoerce, self).setUp()
        self.mutable_dict = MutableDict()

    def test_coerce_mutable_dict(self, m_coerce):
        dct = MutableDict()
        self.assertIsInstance(
            self.mutable_dict.coerce('key', dct), MutableDict)
        self.assertFalse(m_coerce.called)

    def test_coerce_dict(self, m_coerce):
        dct = dict()
        self.assertIsInstance(
            self.mutable_dict.coerce('key', dct), MutableDict)
        self.assertFalse(m_coerce.called)

    def test_coerce_not_acceptable_object(self, m_coerce):
        m_coerce.return_value = None
        obj = list()
        self.mutable_dict.coerce('key', obj)
        m_coerce.assert_called_once_with('key', obj)


class TestMutableBase(BaseUnitTest):
    def setUp(self):
        self.standard = None
        self.mutable_obj = None

    def _assert_call_object_changed_once(self, m_changed):
        m_changed.assert_called_once_with()
        self.assertItemsEqual(self.standard, self.mutable_obj)

    def _assert_object_not_changed(self, m_changed):
        self.assertFalse(m_changed.called)
        self.assertItemsEqual(self.standard, self.mutable_obj)

    def _check(self, method, *args, **kwargs):
        with patch('sqlalchemy.ext.mutable.Mutable.changed') as m_changed:
            self.assertEqual(
                getattr(self.mutable_obj, method)(*args, **kwargs),
                getattr(self.standard, method)(*args, **kwargs))
            self._assert_call_object_changed_once(m_changed)

    def _check_failure(self, error, method, *args, **kwargs):
        with patch('sqlalchemy.ext.mutable.Mutable.changed') as m_changed:
            self.assertRaises(
                error, getattr(self.mutable_obj, method), *args, **kwargs)
            self._assert_object_not_changed(m_changed)


class TestMutableDictBase(TestMutableBase):
    def setUp(self):
        super(TestMutableDictBase, self).setUp()
        self.standard = {'1': 1}
        self.mutable_obj = MutableDict()
        self.mutable_obj.update(self.standard)


class TestMutableDict(TestMutableDictBase):
    def setUp(self):
        super(TestMutableDict, self).setUp()

    def test_initialize(self):
        with patch('sqlalchemy.ext.mutable.Mutable.changed') as m_changed:
            MutableDict(key1='value1', key2='value2')
            self._assert_object_not_changed(m_changed)

    def test_setitem(self):
        self._check('__setitem__', '2', 2)

    def test_setitem_failure(self):
        self._check_failure(TypeError, '__setitem__', {}, 2)

    def test_setdefault(self):
        self._check('setdefault', '2')

    def test_setdefault_with_default(self):
        self._check('setdefault', '2', 4)

    def test_setdefault_with_default_dict(self):
        with patch('sqlalchemy.ext.mutable.Mutable.changed') as m_changed:
            self.mutable_obj.setdefault('num', 1)
            self.mutable_obj.setdefault('num', 2)
            self.assertEqual(m_changed.call_count, 1)
            self.assertEqual(1, self.mutable_obj['num'])

    def test_setdefault_failure(self):
        self._check_failure(TypeError, 'setdefault', {})

    def test_delitem(self):
        self._check('__delitem__', '1')

    def test_delitem_failure(self):
        self._check_failure(KeyError, '__delitem__', '2')

    def test_update(self):
        self._check('update', {'1': 2, '2': 3})

    def test_update_failure(self):
        self._check_failure(TypeError, 'update', 0)

    def test_clear(self):
        self._check('clear')

    def test_pop_existing(self):
        self._check('pop', '1')

    def test_pop_existing_with_default(self):
        self._check('pop', '1', None)

    def test_pop_not_existing(self):
        self._check_failure(KeyError, 'pop', '2')

    def test_pop_not_existing_with_default(self):
        self._check('pop', '2', {})

    def test_popitem(self):
        self._check('popitem')
        self._check_failure(KeyError, 'popitem')


@patch('nailgun.db.sqlalchemy.models.mutable.MutableDict.changed')
class TestMutableDictIntegration(TestMutableDictBase):
    def setUp(self):
        super(TestMutableDictIntegration, self).setUp()

    def test_getstate(self, m_changed):
        self.assertIsInstance(self.mutable_obj.__getstate__(), dict)
        self._assert_object_not_changed(m_changed)

    def test_setstate(self, m_changed):
        dct = {'1': 2, '2': 3}
        self.standard.update(dct)
        self.mutable_obj.__setstate__(dct)
        self._assert_call_object_changed_once(m_changed)

    @patch('nailgun.db.sqlalchemy.models.mutable.MutableDict.__deepcopy__')
    def test_copy(self, m_deepcopy, _):
        m_deepcopy.return_value = Mock()
        clone = copy(self.mutable_obj)
        self.assertEqual(clone, m_deepcopy.return_value)
        self.assertTrue(m_deepcopy.called)

    def test_deep_copy(self, m_changed):
        dct = MutableDict({'1': 'element1', '2': 'element2'})
        self.mutable_obj['2'] = dct

        m_changed.reset_mock()
        clone = deepcopy(self.mutable_obj)
        self.assertEqual(0, m_changed.call_count)
        dct['1'] = 'new_element'
        self.assertEqual(clone['2']['1'], 'element1')
        self.assertEqual(self.mutable_obj['2']['1'], 'new_element')


@patch('sqlalchemy.ext.mutable.Mutable.coerce')
class TestMutableListCoerce(BaseUnitTest):
    def setUp(self):
        self.mutable_list = MutableList()

    def test_coerce_mutable_list(self, m_coerce):
        lst = MutableList()
        self.assertIsInstance(
            self.mutable_list.coerce('key', lst), MutableList)
        self.assertFalse(m_coerce.called)

    def test_coerce_list(self, m_coerce):
        lst = list()
        self.assertIsInstance(
            self.mutable_list.coerce('key', lst), MutableList)
        self.assertFalse(m_coerce.called)

    def test_coerce_not_acceptable_object(self, m_coerce):
        m_coerce.return_value = None
        obj = dict()
        self.mutable_list.coerce('key', obj)
        m_coerce.assert_called_once_with('key', obj)


class TestMutableListBase(TestMutableBase):
    def setUp(self):
        super(TestMutableListBase, self).setUp()
        self.standard = ['element1', 'element2']
        self.mutable_obj = MutableList()
        self.mutable_obj.extend(self.standard)


class TestMutableList(TestMutableListBase):
    def setUp(self):
        super(TestMutableList, self).setUp()

    def test_initialize(self):
        with patch('sqlalchemy.ext.mutable.Mutable.changed') as m_changed:
            MutableList([1, 2, 3])
            self._assert_object_not_changed(m_changed)

    def test_append(self):
        self._check('append', 'element')

    def test_extend(self):
        self._check('extend', ('element3', 'element4', 'element5'))

    def test_extend_failure(self):
        self._check_failure(TypeError, 'extend', None)

    def test_insert(self):
        self._check('insert', 1, 'new_element')

    def test_insert_failure(self):
        self._check_failure(TypeError, 'insert', None, 'element')

    def test_pop_default(self):
        self._check('pop')

    def test_pop_of_specified_element(self):
        self._check('pop', 0)

    def test_pop_wrong_index_type(self):
        self._check_failure(TypeError, 'pop', 'str')

    def test_pop_out_of_range(self, ):
        self._check_failure(IndexError, 'pop', 2)

    def test_pop_default_from_empty_list(self):
        self.standard = []
        self.mutable_obj = MutableList()
        self._check_failure(IndexError, 'pop')

    def test_remove(self):
        self._check('remove', 'element1')

    def test_remove_failure(self):
        self._check_failure(ValueError, 'remove', None)

    def test_set_item_failure(self):
        self._check_failure(IndexError, '__setitem__', 2, 'element')

    def test_del_item(self):
        self._check('__delitem__', 1)

    def test_del_item_failure(self):
        self._check_failure(IndexError, '__delitem__', 2)

    def test_set_state_failure(self):
        self._check_failure(TypeError, '__setstate__', None)

    def test_set_slice(self):
        self._check('__setslice__', 0, 2, ('element',))

    def test_set_slice_failure(self):
        self._check_failure(TypeError, '__setslice__', 0, 5, None)

    def test_del_slice(self):
        self._check('__delslice__', 0, 2)

    def test_del_slice_failure(self):
        self._check_failure(TypeError, '__delslice__', 0, None)


@patch('nailgun.db.sqlalchemy.models.mutable.MutableList.changed')
class TestMutableListIntegration(TestMutableListBase):
    def setUp(self):
        super(TestMutableListIntegration, self).setUp()

    def test_set_item_operator(self, m_changed):
        self.mutable_obj[0] = 'new_element'
        self.standard[0] = 'new_element'
        self._assert_call_object_changed_once(m_changed)

    def test_del_operator(self, m_changed):
        del self.mutable_obj[0]
        del self.standard[0]
        self._assert_call_object_changed_once(m_changed)

    def test_get_state(self, m_changed):
        self.assertIsInstance(self.mutable_obj.__getstate__(), list)
        self._assert_object_not_changed(m_changed)

    def test_set_state(self, m_changed):
        self.mutable_obj.__setstate__([])
        self.standard = []
        self._assert_call_object_changed_once(m_changed)

    def test_set_slice_operator(self, m_changed):
        self.mutable_obj[0:2] = ['new_element']
        self.standard[0:2] = ['new_element']
        self._assert_call_object_changed_once(m_changed)

        m_changed.reset_mock()
        self.mutable_obj[:] = ["again_new_element"]
        self.standard[:] = ["again_new_element"]
        self._assert_call_object_changed_once(m_changed)

    def test_del_slice_operator(self, m_changed):
        del self.mutable_obj[0:2]
        del self.standard[0:2]
        self._assert_call_object_changed_once(m_changed)

    @patch('nailgun.db.sqlalchemy.models.mutable.MutableList.__deepcopy__')
    def test_copy(self, m_deepcopy, _):
        m_deepcopy.return_value = Mock()
        clone = copy(self.mutable_obj)
        self.assertEqual(clone, m_deepcopy.return_value)
        self.assertTrue(m_deepcopy.called)

    def test_deep_copy(self, m_changed):
        lst = MutableList(('element1', 'element2'))
        self.mutable_obj.insert(0, lst)

        m_changed.reset_mock()
        clone = deepcopy(self.mutable_obj)
        self.assertEqual(0, m_changed.call_count)

        lst[0] = 'new_element'
        self.assertEqual(clone[0][0], 'element1')
        self.assertEqual(self.mutable_obj[0][0], 'new_element')
