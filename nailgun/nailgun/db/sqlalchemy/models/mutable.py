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
import yaml

from sqlalchemy.ext.mutable import Mutable
from sqlalchemy.ext.mutable import MutableDict as MutableDictBase


class MutableDict(MutableDictBase):
    # TODO(vkaplov): delete this class after methods pop and popitem
    # will be implemented in sqlalchemy lib.
    # https://bitbucket.org/zzzeek/sqlalchemy/issues/3605

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


# Registering MutableDict representer for yaml safe dumper
yaml.SafeDumper.add_representer(
    MutableDict, yaml.representer.SafeRepresenter.represent_dict)


class MutableList(Mutable, list):
    # TODO(fzhadaev): delete this class after it will be
    #                 implemented in sqlalchemy lib.
    # https://bitbucket.org/zzzeek/sqlalchemy/issues/3297

    @classmethod
    def coerce(cls, key, value):
        """Convert plain lists to MutableList.

        :param key: string name of the ORM-mapped attribute being set.
        :param value: the incoming value.
        :return: the method should return the coerced value
        :raises ValueError: if the coercion cannot be completed.
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

    def __setslice__(self, first, last, sequence):
        """Envoke setslice and emit change events.

        :param first: first element index
        :param last: last (not included) element index
        :param sequence: elements that to be inserted
        """

        list.__setslice__(self, first, last, sequence)
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
        clone = MutableList()
        clone.__setstate__(value)
        return clone

    def __deepcopy__(self, memo, _deepcopy=copy.deepcopy):
        """Recursive copy each element."""
        clone = MutableList()
        clone.__setstate__((_deepcopy(x, memo) for x in self))
        return clone


# Registering MutableList representer for yaml safe dumper
yaml.SafeDumper.add_representer(
    MutableList, yaml.representer.SafeRepresenter.represent_list)
