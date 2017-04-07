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

import collections
import itertools
import yaml


class UnionDict(collections.Mapping):
    """Object, which acts like read-only union of several dicts.

    This is an object which acts like a deep merge of several
    dicts. It's needed to replace real dict, merged with help
    of utils.dict_merge in LCM code.
    """
    def __init__(self, *dicts):
        for d in dicts:
            if not isinstance(d, dict):
                raise ValueError("UnionDict can only be apllied to dicts.")

        self.dicts = list(dicts)
        self.dicts.reverse()
        self.keys = lambda: set(itertools.chain.from_iterable(dicts))

    def __getitem__(self, key):
        values = []
        for d in self.dicts:
            try:
                value = d[key]
            except KeyError:
                continue

            values.append(value)
            if not isinstance(value, dict):
                return values[0]

        if len(values) == 0:
            raise KeyError(key)
        elif len(values) == 1:
            return values[0]

        values.reverse()
        return UnionDict(*values)

    def __iter__(self):
        return iter(self.keys)

    def __len__(self):
        return len(self.keys)

    def __repr__(self):
        items = ['{!r}: {!r}'.format(k, v) for k, v in self.items()]
        return '{{{}}}'.format(', '.join(items))


def uniondict_representer(dumper, data):
    return dumper.represent_mapping(u'tag:yaml.org,2002:map', data)


yaml.add_representer(UnionDict, uniondict_representer)
