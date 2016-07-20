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

import yaml

from nailgun.test.base import BaseTestCase
from nailgun.utils.uniondict import UnionDict


YAML_STR_EXPECTED = """a: 1
b: 3
c:
  x: 10
  y: 20
d: 4"""


class TestUnionDict(BaseTestCase):

    def test_base(self):
        d1 = {'a': 1, 'b': 2}
        d2 = {'c': 3, 'd': 4}

        d = UnionDict(d1, d2)
        self.assertEqual(d['a'], 1)
        self.assertEqual(d['b'], 2)
        self.assertEqual(d['c'], 3)
        self.assertEqual(d['d'], 4)

    def test_override(self):
        d1 = {'a': 1}
        d2 = {'a': 2}

        d = UnionDict(d1, d2)
        self.assertEqual(d['a'], 2)

        d = UnionDict(d2, d1)
        self.assertEqual(d['a'], 1)

    def test_override_dict(self):
        d1 = {'a': {'x': 10}}
        d2 = {'a': 1}

        d = UnionDict(d1, d2)
        self.assertEqual(d['a'], 1)

    def test_merge(self):
        d1 = {'a': {'x': 10}}
        d2 = {'a': {'y': 20}}

        d = UnionDict(d1, d2)
        self.assertIsInstance(d['a'], UnionDict)
        self.assertEqual(d['a']['x'], 10)
        self.assertEqual(d['a']['y'], 20)

    def test_yaml_dump(self):
        d1 = {'a': 1, 'b': 2, 'c': {'x': 10}}
        d2 = {'b': 3, 'd': 4, 'c': {'y': 20}}

        d = UnionDict(d1, d2)
        yaml_str = yaml.dump(d, default_flow_style=False).strip()
        self.assertEqual(yaml_str, YAML_STR_EXPECTED)
