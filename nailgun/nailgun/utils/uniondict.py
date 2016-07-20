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
import yaml


class UnionDict(collections.Mapping):
    """Object, which acts like union of two dicts.

    This is an object which acts like a deep merge of two
    dicts. It's needed to replace real dict, merged with help
    of utils.dict_merge in LCM code.
    """
    def __init__(self, a, b):
        if not all(map(lambda x: isinstance(x, dict), [a, b])):
            raise ValueError("UnionDict can only be allied to 2 dicts.")

        self.a = a
        self.b = b
        self.keys = set(self.a.keys()) | set(self.b.keys())

    def __getitem__(self, key):
        if key not in self.b:
            return self.a[key]
        if key not in self.a:
            return self.b[key]
        if not isinstance(self.b[key], dict):
            return self.b[key]
        return UnionDict(self.a[key], self.b[key])

    def __iter__(self):
        return iter(self.keys)

    def __len__(self):
        return len(self.keys)


def uniondict_representer(dumper, data):
    return dumper.represent_mapping(u'tag:yaml.org,2002:map', data)


yaml.add_representer(UnionDict, uniondict_representer)
