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

        self.dicts = dicts
        self.keys = set(itertools.chain.from_iterable(
            [d.keys() for d in dicts]))

    def __getitem__(self, key):
        if key not in self.keys:
            raise KeyError(key)

        for i in range(1, len(self.dicts)):
            d = self.dicts[-i]
            if key not in d:
                continue

            v = d[key]
            if not isinstance(v, dict):
                return v

            rest = [x[key] for x in self.dicts[:-1]
                    if key in x and isinstance(x[key], dict)]
            if not rest:
                return v
            return UnionDict(*rest + [v])

        return self.dicts[0][key]

    def __iter__(self):
        return iter(self.keys)

    def __len__(self):
        return len(self.keys)


def uniondict_representer(dumper, data):
    return dumper.represent_mapping(u'tag:yaml.org,2002:map', data)


yaml.add_representer(UnionDict, uniondict_representer)
