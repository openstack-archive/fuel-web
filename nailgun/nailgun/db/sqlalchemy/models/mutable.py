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

from sqlalchemy.ext.mutable import Mutable


class MutableList(Mutable, list):
    # TODO(fzhadaev): delete this class after it will be
    #                 implemented in sqlalchemy lib.
    # https://bitbucket.org/zzzeek/sqlalchemy/issues/3297

    @classmethod
    def coerce(cls, key, value):
        """Convert plain lists to MutableList.

        :param key: string name of the ORM-mapped attribute being set.
        :param value: the incoming value.
        :return: the method should return the coerced value, or raise
         ValueError if the coercion cannot be completed.
        """

        if not isinstance(value, MutableList):
            if isinstance(value, list):
                return MutableList(value)

            # this call will raise ValueError
            return Mutable.coerce(key, value)
        else:
            return value

    def append(self, value):
        """Append value to end and emit change events.

        :param value: element value
        """

        list.append(self, value)
        self.changed()

    def extend(self, iterable):
        """Extend list and emit change events.

        :param iterable: iterable on elements
        """

        list.extend(self, iterable)
        self.changed()

    def insert(self, index, value):
        """Insert value before index and emit change events.

        :param index: index of next element
        :param value: value of inserting element
        """

        list.insert(self, index, value)
        self.changed()

    def pop(self, index=None):
        """Pop element and emit change events if item removed.

        :param index: index of element (default last)
        :return: element or raises IndexError if list is empty or
        index is out of range.
        """

        result = list.pop(self) if index is None else list.pop(self, index)
        self.changed()
        return result

    def remove(self, value):
        """Remove first occurrence of value.

        Raises ValueError if the value is not present.
        If occurrence removed, then emit change events.

        :param value: value of element
        """

        list.remove(self, value)
        self.changed()

    def __setitem__(self, key, value):
        """Detect list set events and emit change events.

        :param key: index of element
        :param value: new value of element
        """

        list.__setitem__(self, key, value)
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
        self.changed()

    @classmethod
    def __copy__(cls, value):
        """Use copy via constructor."""

        return MutableList(value)

    def __deepcopy__(self, memo, _deepcopy=copy.deepcopy):
        """Recursive copy each element."""

        return MutableList(_deepcopy(x, memo) for x in self)
