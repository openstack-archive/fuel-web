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

from nailgun.db.sqlalchemy.models.mutable import Mutable
from nailgun.db.sqlalchemy.models.mutable import MutableDict
from nailgun.db.sqlalchemy.models.mutable import MutableList
from nailgun.test.base import BaseUnitTest


class TestMutable(BaseUnitTest):
    def setUp(self):
        self.parents = {'parent': 'key'}
        self.mutable = Mutable()
        self.mutable._parents = self.parents

    def _check_cast(self, value, expected_type):
        result = self.mutable.cast(value)
        self.assertIsInstance(result, expected_type)
        self.assertIs(result._parents, self.mutable._parents)
        self.assertItemsEqual(result, value)

    def test_cast_list(self):
        self._check_cast([1, 2, 3], MutableList)

    def test_cast_dict(self):
        self._check_cast({'1': 1, '2': 2}, MutableDict)

    def test_cast_mutable_list(self):
        self._check_cast(MutableList([1, 2, 3]), MutableList)

    def test_cast_mutable_dict(self):
        self._check_cast(MutableDict({'1': 1, '2': 2}), MutableDict)

    def test_cast_simple_type(self):
        result = self.mutable.cast(1)
        self.assertIsInstance(result, int)
        self.assertEqual(result, 1)


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
            self._assert_call_object_changed_once(m_changed)

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
            self.mutable_obj.setdefault('2', dict())
            # 'changed' method called twice:
            #  - during casting default dict to MutableDict for new object
            #  - in setdefault method for 'mutable_obj'
            self.assertEqual(m_changed.call_count, 2)

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

    def test_copy(self, m_changed):
        clone = copy(self.mutable_obj)
        self.assertEqual(clone, self.mutable_obj)
        m_changed.assert_called_once_with()

    def test_deep_copy(self, m_changed):
        dct = MutableDict({'1': 'element1', '2': 'element2'})
        self.mutable_obj['2'] = dct

        m_changed.reset_mock()
        clone = deepcopy(self.mutable_obj)
        # changed should calls two times
        # - root cloned dict (clone)
        # - mutable dict element in root dict (cloned dct)
        self.assertEqual(m_changed.call_count, 2)

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
            self._assert_call_object_changed_once(m_changed)

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

    def test_copy(self, m_changed):
        clone = copy(self.mutable_obj)
        self.assertEqual(clone, self.mutable_obj)
        m_changed.assert_called_once_with()

    def test_deep_copy(self, m_changed):
        lst = MutableList(('element1', 'element2'))
        self.mutable_obj.insert(0, lst)

        m_changed.reset_mock()
        clone = deepcopy(self.mutable_obj)
        # changed should calls two times
        # - root cloned list (clone)
        # - mutable list element in root list (cloned lst)
        self.assertEqual(m_changed.call_count, 2)

        lst[0] = 'new_element'
        self.assertEqual(clone[0][0], 'element1')
        self.assertEqual(self.mutable_obj[0][0], 'new_element')


class TestComplexDataStructures(BaseUnitTest):
    def setUp(self):
        lst = [
            {'1': 1, '2': 2},
            MutableDict({'1': 1, '2': 2}),
            MutableList([1, 2, 3]),
            '123'
        ]
        # create list with three levels of nesting
        complex_list = lst + [lst + [lst]]
        self.mutable_list = MutableList(complex_list)

        dct = {
            '1': [1, 2],
            '2': MutableList([1, 3]),
            '3': MutableDict({'1': 1, '2': 2}),
            '4': '123'
        }
        # create dict with three levels of nesting
        complex_dict = dict(dct)
        complex_dict.setdefault('5', copy(dct))
        complex_dict['5'].setdefault('5', copy(dct))
        self.mutable_dict = MutableDict(complex_dict)

        self.lst = [1, [1, 2, 3], {'1': 1, '2': 2}]
        self.dct = {'1': 1, '2': [1, 2, 3], '3': {'1': 1, '2': 2}}

    def _validate_data(self, data):
        """Iterative data validation

        Check that there're no builtin list or dict in data
        :param data: data to validate
        """
        elements = []
        while True:
            self.assertNotIn(type(data), (dict, list))
            if isinstance(data, dict):
                self.assertIsInstance(data, MutableDict)
                elements.extend([value for key, value in data.items()])
            if isinstance(data, list):
                self.assertIsInstance(data, MutableList)
                elements.extend(data)
            if not elements:
                break
            data = elements.pop()

    def _check(self, obj, method, *args, **kwargs):
        getattr(obj, method)(*args, **kwargs)
        self._validate_data(obj)

    def test_append_to_first_level(self):
        self._check(self.mutable_list, 'append', self.lst)

    def test_append_to_second_level(self):
        self._check(self.mutable_list[2], 'append', self.lst)

    def test_append_to_third_level(self):
        self._check(self.mutable_list[4][4], 'append', self.lst)

    def test_extend_first_level(self):
        self._check(self.mutable_list, 'extend', self.lst)

    def test_extend_second_level(self):
        self._check(self.mutable_list[2], 'extend', self.lst)

    def test_third_third_level(self):
        self._check(self.mutable_list[4][4], 'extend', self.lst)

    def test_insert_to_first_level(self):
        self._check(self.mutable_list, 'insert', 2, self.lst)

    def test_insert_to_second_level(self):
        self._check(self.mutable_list[2], 'insert', 2, self.lst)

    def test_insert_to_third_level(self):
        self._check(self.mutable_list[4][4], 'insert', 2, self.lst)

    def test_setitem_to_first_level(self):
        self._check(self.mutable_list, '__setitem__', 1, self.lst)

    def test_setitem_to_second_level(self):
        self._check(self.mutable_list[2], '__setitem__', 1, self.lst)

    def test_setitem_to_third_level(self):
        self._check(self.mutable_list[4][4], '__setitem__', 1, self.lst)

    def test_setslice_to_first_level(self):
        self._check(self.mutable_list, '__setslice__', 0, 3, self.lst)

    def test_setslice_to_second_level(self):
        self._check(self.mutable_list[2], '__setslice__', 0, 3, self.lst)

    def test_setslice_to_third_level(self):
        self._check(self.mutable_list[4][4], '__setslice__', 0, 3, self.lst)
