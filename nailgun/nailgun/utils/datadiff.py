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

from difflib import SequenceMatcher
try:
    from collections.abc import Hashable
    from collections.abc import Iterable
except ImportError:
    from collections import Hashable
    from collections import Iterable

import six


class DataDiff(object):
    def __init__(self, added=None, deleted=None):
        self.added = added
        self.deleted = deleted


def diff(a, b):
    """Calculates plain diff(not recursively).

    :param a: original data
    :param b: modified data
    :return: the DataDiff objects, that shows what was changed in a
    """
    if isinstance(a, six.string_types) or isinstance(b, six.string_types):
        a = a and a.splitlines()
        b = b and b.splitlines()
        diff_impl = diff_array
    elif isinstance(a, dict) or isinstance(b, dict):
        a = _ensure_typeof(a, dict)
        b = _ensure_typeof(b, dict)
        diff_impl = diff_dict
    elif isinstance(a, (set, frozenset)) or isinstance(b, (set, frozenset)):
        a = _ensure_typeof(a, frozenset)
        b = _ensure_typeof(b, frozenset)
        diff_impl = diff_set
    elif isinstance(a, list) or isinstance(b, list):
        a = _ensure_typeof(a, list)
        b = _ensure_typeof(b, list)
        diff_impl = diff_array
    elif isinstance(a, Iterable) or isinstance(b, Iterable):
        a = a and list(a)
        b = b and list(b)
        diff_impl = diff_array
    else:
        diff_impl = diff_any

    if a is None:
        return DataDiff() if b is None else DataDiff(added=b)
    if b is None:
        return DataDiff(deleted=a)

    return diff_impl(a, b)


def diff_any(a, b):
    return DataDiff() if a == b else DataDiff(added=b, deleted=a)


def diff_array(a, b):
    hashable_a = do_hashable(a)
    hashable_b = do_hashable(b)

    sm = SequenceMatcher(a=hashable_a, b=hashable_b)
    added = []
    deleted = []
    for change, i1, i2, j1, j2 in sm.get_opcodes():
        if change == 'insert':
            added.extend(b[j1:j2])
        elif change == 'delete':
            deleted.extend(a[i1:i2])
        elif change == 'replace':
            for a2, b2 in six.moves.zip(a[i1:i2], b[j1:j2]):
                added.append(a2)
                deleted.append(b2)

            if i2 - i1 > j2 - j1:
                common_length = j2 - j1
                added.extend(a[i1 + common_length:i2])
            if i2 - i1 < j2 - j1:
                common_length = i2 - i1
                deleted.extend(b[j1 + common_length:j2])
    return DataDiff(added=added, deleted=deleted)


def diff_dict(a, b):
    added = {}
    deleted = {}
    for key in a:
        if key not in b:
            deleted[key] = a[key]
        elif a[key] != b[key]:
            deleted[key] = a[key]
            added[key] = b[key]
    for key in b:
        if key not in a:
            added[key] = b[key]
    return DataDiff(added=added, deleted=deleted)


def diff_set(a, b):
    return DataDiff(added=b - a, deleted=a - b)


def do_hashable(data):
    # convert top-level container
    if isinstance(data, Hashable):
        return data

    if isinstance(data, dict):
        return frozenset(do_hashable(x) for x in six.iteritems(data))
    if isinstance(data, set):
        return frozenset(do_hashable(x) for x in data)
    if isinstance(data, Iterable):
        return tuple(do_hashable(x) for x in data)

    # this raises error if data is not hashable actually
    hash(data)
    return data


def _ensure_typeof(data, expected_type):
    """Checks that data has type expected_type.

    :param data: the data
    :param expected_type: the expected type
    :return: the data converted to type expected_type
    :raises TypeError: if conversion is not allowed
    """
    if data is None:
        return None

    if not isinstance(data, expected_type):
        try:
            return expected_type(data)
        except TypeError:
            raise TypeError(
                "Cannot convert {0} to {1}".format(type(data), expected_type)
            )
    return data
