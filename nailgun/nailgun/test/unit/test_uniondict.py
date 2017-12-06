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

from oslo_serialization import jsonutils

from nailgun.test.base import BaseTestCase
from nailgun.utils.uniondict import UnionDict


class TestUnionDict(BaseTestCase):

    D1 = {'a': 1, 'b': 2, 'c': {'x': 10}}
    D2 = {'b': 3, 'd': 4, 'c': {'y': 20}}
    D3 = {'e': 5, 'f': 6, 'c': {'z': 30}}
    D = {'a': 1, 'b': 3, 'c': {'x': 10, 'y': 20, 'z': 30},
         'd': 4, 'e': 5, 'f': 6}

    YAML_STR_EXPECTED = """a: 1
b: 3
c:
  x: 10
  y: 20
  z: 30
d: 4
e: 5
f: 6"""

    JSON_STR_EXPECTED = ('{"c": {"z": 30, "y": 20, "x": 10}, '
                         '"b": 3, "a": 1, "f": 6, "e": 5, "d": 4}')

    def test_base(self):
        d1 = {'a': 1, 'b': 2}
        d2 = {'c': 3, 'd': 4}
        d3 = {'e': 5, 'f': 6}

        d = UnionDict(d1, d2, d3)
        self.assertEqual(d['a'], 1)
        self.assertEqual(d['b'], 2)
        self.assertEqual(d['c'], 3)
        self.assertEqual(d['d'], 4)
        self.assertEqual(d['e'], 5)
        self.assertEqual(d['f'], 6)
        self.assertRaises(KeyError, lambda: d[0])

    def test_override(self):
        d1 = {'a': 1, 'b': 1}
        d2 = {'a': 2, 'b': 2}
        d3 = {'a': 3}

        d = UnionDict(d1, d2, d3)
        self.assertEqual(d['a'], 3)
        self.assertEqual(d['b'], 2)

        d = UnionDict(d3, d2, d1)
        self.assertEqual(d['a'], 1)
        self.assertEqual(d['b'], 1)

    def test_override_dict(self):
        d1 = {'a': {'x': 10}}
        d2 = {'a': 1}

        d = UnionDict(d1, d2)
        self.assertEqual(d['a'], 1)

        d = UnionDict(d2, d1)
        self.assertEqual(d['a'], {'x': 10})

    def test_merge(self):
        d1 = {'a': {'x': 10}}
        d2 = {'a': {'y': 20}}
        d3 = {'a': {'z': 30}}

        d = UnionDict(d1, d2, d3)
        self.assertIsInstance(d['a'], UnionDict)
        self.assertEqual(d['a']['x'], 10)
        self.assertEqual(d['a']['y'], 20)
        self.assertEqual(d['a']['z'], 30)

    def test_yaml_dump(self):
        d = UnionDict(self.D1, self.D2, self.D3)
        yaml_str = yaml.dump(d, default_flow_style=False).strip()
        self.assertEqual(yaml_str, self.YAML_STR_EXPECTED)

    def test_json_dump(self):
        d = UnionDict(self.D1, self.D2, self.D3)
        json_str = jsonutils.dumps(d).strip()
        self.assertEqual(jsonutils.loads(json_str),
                         jsonutils.loads(self.JSON_STR_EXPECTED))

    def test_repr(self):
        d = UnionDict(self.D1, self.D2, self.D3)
        self.assertEqual(eval(repr(d)), self.D)

    def test_keys(self):
        ud = UnionDict({'a': 1, 'b': 2, 'c': 3},
                       {'b': 2, 'c': 3, 'd': 4},
                       {'e': 5})
        self.assertEqual(ud.keys(), {'a', 'b', 'c', 'd', 'e'})
