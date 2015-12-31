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

import copy
import six

from sqlalchemy.ext.mutable import Mutable as MutableBase


class Mutable(MutableBase):
    def __init__(self, *args, **kwargs):
        super(Mutable, self).__init__(*args, **kwargs)
        self.__setstate__(self)

    def __setstate__(self, _):
        """This method should be re-implemented in subclasses.

        By default do nothing
        :param _: new state of object
        :return: None
        """
        pass

    @classmethod
    def _coerce(cls, key, value, coerce_type):
        """Convert plain dictionaries to MutableDict.

        :param key: string name of the ORM-mapped attribute being set.
        :param value: the incoming value.
        :param coerce_type: type, that should be coerced
        :return: the method should return the coerced value
        :raises ValueError: if the coercion cannot be completed.
        """
        if not isinstance(value, cls):
            if isinstance(value, coerce_type):
                return cls(value)

            # this call will raise ValueError
            return MutableBase.coerce(key, value)
        return value

    @staticmethod
    def mutable_cast_map():
        yield dict, MutableDict
        yield list, MutableList

    def cast(self, value):
        """Cast type of value.

        If value of MutableBase type, then just update the '_parents'.
        If value of type from 'mutable_cast_map', then convert value to
        corresponding mutable type and assign the '_parents'.
        In all other cases return value without changes.
        :param value: value to be casted
        :return: casted value
        """
        if isinstance(value, MutableBase):
            value._parents = self._parents
            return value

        for original, mutable in self.mutable_cast_map():
            if isinstance(value, original):
                value = mutable(value)
                value._parents = self._parents
                return value

        return value


class MutableDict(Mutable, dict):
    @classmethod
    def coerce(cls, key, value):
        """Convert plain dictionaries to MutableDict.

        :param key: string name of the ORM-mapped attribute being set.
        :param value: the incoming value.
        :return: the method should return the coerced value
        """
        return cls._coerce(key, value, dict)

    def __setitem__(self, key, value):
        """Detect dict set events and emit change events.

        :param key: key of element
        :param value: new value of element
        """
        dict.__setitem__(self, key, self.cast(value))
        self.changed()

    def setdefault(self, key, default=None):
        """Detect dict setdefault events and emit change events.

        :param key: key in the dictionary
        :param default: default value.
        :return: if key is in the dictionary return value, otherwise default.
        """
        result = dict.setdefault(self, key, self.cast(default))
        self.changed()
        return result

    def __delitem__(self, key):
        """Detect dictionary del events and emit change events.

        :param key: key in the dictionary
        """
        dict.__delitem__(self, key)
        self.changed()

    def update(self, *args, **kwargs):
        """Detect dictionary update events and emit change events.

        :param args: accept the same args as builtin dict
        :param kwargs: accept the same kwargs as builtin dict
        """
        tmp = dict(*args, **kwargs)
        dict.update(self, {k: self.cast(v) for k, v in six.iteritems(tmp)})
        self.changed()

    def clear(self):
        """Detect dictionary clear events and emit change events."""
        dict.clear(self)
        self.changed()

    def __getstate__(self):
        """Get state as builtin dict

        :return: current state
        """
        return dict(self)

    def __setstate__(self, state):
        """Detect setstate event and emit change events.

        :param state: new object state
        """
        self.update(state)

    def pop(self, *args):
        """Pop element and emit change events if item removed.

        :param args: (key, default) 'default' is optional
        :return: element
        :raises KeyError: if dict is empty or element not found.
        """
        result = dict.pop(self, *args)
        self.changed()
        return result

    def popitem(self):
        """Pop arbitrary element and emit change events if item removed.

        :return: (key, value)
        :raises KeyError: if dict is empty.
        """
        result = dict.popitem(self)
        self.changed()
        return result

    @classmethod
    def __copy__(cls, value):
        """Create and return copy of value.

        :param value: MutableDict object
        """
        return MutableDict(value)

    def __deepcopy__(self, memo, _deepcopy=copy.deepcopy):
        """Recursive copy each element."""
        return MutableDict({k: _deepcopy(v, memo) for k, v in self.items()})


class MutableList(Mutable, list):
    @classmethod
    def coerce(cls, key, value):
        """Convert plain lists to MutableList.

        :param key: string name of the ORM-mapped attribute being set.
        :param value: the incoming value.
        :return: the method should return the coerced value
        """
        return cls._coerce(key, value, list)

    def append(self, value):
        """Append value to end and emit change events.

        :param value: element value
        """
        list.append(self, self.cast(value))
        self.changed()

    def extend(self, iterable):
        """Extend list and emit change events.

        :param iterable: iterable on elements
        """
        casted_elements = (self.cast(value) for value in iterable)
        list.extend(self, casted_elements)
        self.changed()

    def insert(self, index, value):
        """Insert value before index and emit change events.

        :param index: index of next element
        :param value: value of inserting element
        """
        list.insert(self, index, self.cast(value))
        self.changed()

    def pop(self, index=-1):
        """Pop element and emit change events if item removed.

        :param index: index of element (default last)
        :return: element
        :raises IndexError: if list is empty or index is out of range.
        """
        result = list.pop(self, index)
        self.changed()
        return result

    def remove(self, value):
        """Remove first occurrence of value.

        If occurrence removed, then emit change events.

        :param value: value of element
        :raises ValueError: if the value is not present.
        """
        list.remove(self, value)
        self.changed()

    def __setitem__(self, key, value):
        """Detect list set events and emit change events.

        :param key: index of element
        :param value: new value of element
        """
        list.__setitem__(self, key, self.cast(value))
        self.changed()

    def __delitem__(self, key):
        """Detect list del events and emit change events.

        :param key: index of element
        """
        list.__delitem__(self, key)
        self.changed()

    def __getstate__(self):
        """Get state as builtin list

        :return: current state
        """
        return list(self)

    def __setstate__(self, state):
        """Detect setstate event and emit change events.

        :param state: new object state
        """
        self[:] = state

    def __setslice__(self, first, last, sequence):
        """Envoke setslice and emit change events.

        :param first: first element index
        :param last: last (not included) element index
        :param sequence: elements that to be inserted
        """
        casted_sequence = (self.cast(value) for value in sequence)
        list.__setslice__(self, first, last, casted_sequence)
        self.changed()

    def __delslice__(self, first, last):
        """Envoke delslice and emit change events.

        :param first: first element index
        :param last: last (not included) element index
        """
        list.__delslice__(self, first, last)
        self.changed()

    @classmethod
    def __copy__(cls, value):
        """Create and return copy of value.

        :param value: MutableList object
        """
        return MutableList(value)

    def __deepcopy__(self, memo, _deepcopy=copy.deepcopy):
        """Recursive copy each element."""
        return MutableList((_deepcopy(x, memo) for x in self))
