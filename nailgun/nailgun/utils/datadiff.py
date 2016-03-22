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
    if type(a) is not type(b):
        return diff_any(a, b)

    if isinstance(a, six.string_types):
        return diff_array(a.splitlines(), b.splitlines())
    if isinstance(a, dict):
        return diff_dict(a, b)
    if isinstance(a, (set, frozenset)):
        return diff_set(a, b)
    elif isinstance(a, list):
        return diff_array(a, b)
    if isinstance(a, Iterable):
        return diff_array(list(a), list(b))
    return diff_any(a, b)


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
            added.extend(b[j1:j2])
            deleted.extend(a[i1:i2])
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
