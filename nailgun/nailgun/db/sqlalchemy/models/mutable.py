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
import yaml.representer

from sqlalchemy.ext.mutable import Mutable as MutableBase


# TODO(vkaplov) Starting to use native sqlalchemy mutable types after bug fix
# https://bitbucket.org/zzzeek/sqlalchemy/issues/3646
class MutableCollection(MutableBase):
    @classmethod
    def __copy__(cls, value):
        """Create and return deepcopy of value.

        Because of consistency we should to deepcopy Mutable in tree.
        Otherwise depending on level in tree Mutable will reference to
        different structures in database.
        :param value: subclass of Mutable object
        """
        return copy.deepcopy(value)

    def mark_dirty(self):
        """Alias for method changed."""
        self.changed()

    def __setitem__(self, key, value):
        super(MutableCollection, self).__setitem__(key, value)
        self.changed()

    def __delitem__(self, key):
        super(MutableCollection, self).__delitem__(key)
        self.changed()

    def clear(self):
        super(MutableCollection, self).clear()
        self.changed()

    def pop(self, *args):
        result = super(MutableCollection, self).pop(*args)
        self.changed()
        return result


class MutableDict(MutableCollection, dict):
    @classmethod
    def coerce(cls, key, value):
        """Convert plain dictionaries to MutableDict.

        :param key: string name of the ORM-mapped attribute being set.
        :param value: the incoming value.
        :return: the method should return the coerced value
        """
        if not isinstance(value, cls):
            if isinstance(value, dict):
                return cls(value)
            # this call will raise ValueError
            return MutableBase.coerce(key, value)
        return value

    def setdefault(self, key, default=None):
        """Detect dict setdefault events and emit change events.

        :param key: key in the dictionary
        :param default: default value.
        :return: if key is in the dictionary return value, otherwise default.
        """
        try:
            return self[key]
        except KeyError:
            self[key] = default
            return default

    def update(self, *args, **kwargs):
        """Detect dictionary update events and emit change events.

        :param args: accept the same args as builtin dict
        :param kwargs: accept the same kwargs as builtin dict
        """
        dict.update(self, *args, **kwargs)
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

    def popitem(self):
        """Pop arbitrary element and emit change events if item removed.

        :return: (key, value)
        :raises KeyError: if dict is empty.
        """
        result = dict.popitem(self)
        self.changed()
        return result

    def __deepcopy__(self, memo, _deepcopy=copy.deepcopy):
        """Recursive copy each element."""
        return MutableDict({k: _deepcopy(v, memo) for k, v in self.items()})


class MutableList(MutableCollection, list):
    @classmethod
    def coerce(cls, key, value):
        """Convert plain lists to MutableList.

        :param key: string name of the ORM-mapped attribute being set.
        :param value: the incoming value.
        :return: the method should return the coerced value
        """
        if not isinstance(value, cls):
            if isinstance(value, list):
                return cls(value)
            # this call will raise ValueError
            return MutableBase.coerce(key, value)
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

    def remove(self, value):
        """Remove first occurrence of value.

        If occurrence removed, then emit change events.

        :param value: value of element
        :raises ValueError: if the value is not present.
        """
        list.remove(self, value)
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

    def __deepcopy__(self, memo, _deepcopy=copy.deepcopy):
        """Recursive copy each element."""
        return MutableList((_deepcopy(x, memo) for x in self))


# For serialization of custom objects into yaml we need to add
# appropriate representers. yaml library gets the first
# class name from the object MRO and search it in the registered
# representers list. Thus we are adding representers for Mutable
# objects into yaml.
yaml.add_representer(
    MutableDict,
    yaml.representer.SafeRepresenter.represent_dict,
    yaml.SafeDumper
)

yaml.add_representer(
    MutableDict,
    yaml.representer.SafeRepresenter.represent_dict,
    yaml.Dumper
)

yaml.add_representer(
    MutableList,
    yaml.representer.SafeRepresenter.represent_list,
    yaml.SafeDumper
)

yaml.add_representer(
    MutableList,
    yaml.representer.SafeRepresenter.represent_list,
    yaml.Dumper
)
