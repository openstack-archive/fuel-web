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

from mock import Mock
from mock import patch
import os

from nailgun.test.base import BaseTestCase

from nailgun.statistics import errors
from nailgun.statistics import utils


class TestUtilsFunctions(BaseTestCase):

    def test_set_proxy_func(self):
        def check_proxy():
            with utils.set_proxy(new_proxy):
                self.assertEqual(os.environ.get("http_proxy"), new_proxy)
                self.assertEqual(os.environ.get("https_proxy"), new_proxy)

        def raise_inside_context():
            with utils.set_proxy(new_proxy):
                raise Exception("Just an error")

        expected = {"http_proxy": "test_http", "https_proxy": "test_https"}
        new_proxy = "fake_proxy"

        # check that proxy old value is restored
        # after exit from context manager w/ and w/o exception
        with patch.dict("os.environ", expected):
            check_proxy()
            self.assertEqual(os.environ.get("http_proxy"),
                             expected["http_proxy"])
            self.assertEqual(os.environ.get("https_proxy"),
                             expected["https_proxy"])

            self.assertRaisesRegexp(
                Exception, "Just an error", raise_inside_context
            )
            self.assertEqual(os.environ.get("http_proxy"),
                             expected["http_proxy"])
            self.assertEqual(os.environ.get("https_proxy"),
                             expected["https_proxy"])

        # check that env variable is deleted
        # after exit from context manager w/ and w/o exception
        check_proxy()
        self.assertNotIn("http_proxy", os.environ)
        self.assertNotIn("https_proxy", os.environ)

        self.assertRaisesRegexp(
            Exception, "Just an error", raise_inside_context
        )
        self.assertNotIn("http_proxy", os.environ)
        self.assertNotIn("https_proxy", os.environ)

    def test_get_attr_value(self):
        attributes = {
            'a': 'b',
            'c': [
                {'x': 'z', 'y': [{'t': 'u'}, {'v': 'w'}, {'t': 'u0'}]},
                {'x': 'zz', 'y': [{'t': 'uu'}, {'v': 'ww'}]}
            ],
            'd': {'f': 'g', 'k': [0, 1, 2]},
        }
        white_list = (
            utils.WhiteListRule(('a',), 'map_a', None),
            utils.WhiteListRule(('d', 'f'), 'map_f', None),
            utils.WhiteListRule(('d', 'k'), 'map_k_len', len),
            utils.WhiteListRule(('c', 'x'), 'map_x', None),
            utils.WhiteListRule(('c', 'y', 't'), 'map_t', None),
        )

        actual = {}
        for rule in white_list:
            actual[rule.map_to_name] = utils.get_attr_value(
                rule.path, rule.transform_func, attributes)

        expected = {
            'map_f': 'g',
            'map_k_len': 3,
            'map_a': 'b',
            'map_x': ['z', 'zz'],
            'map_t': [['u', 'u0'], ['uu']],
        }
        self.assertDictEqual(actual, expected)

    def test_get_online_controller(self):
        node_name = "test"
        self.env.create(
            nodes_kwargs=[{"online": True,
                           "roles": ["controller"],
                           "name": node_name}]
        )

        cluster = self.env.clusters[0]
        online_controller = utils.get_online_controller(cluster)
        self.assertIsNotNone(online_controller)
        self.assertEqual(online_controller.name, node_name)

        cluster.nodes[0].online = False
        self.assertRaises(errors.NoOnlineControllers,
                          utils.get_online_controller,
                          cluster)

    def test_get_nested_attr(self):
        expected_attr = Mock()
        intermediate_attr = Mock(spec=["expected_attr"])
        containing_obj = Mock(spec=["intermediate_attr"])

        intermediate_attr.expected_attr = expected_attr
        containing_obj.intermediate_attr = intermediate_attr

        existing_attr_path = ["intermediate_attr", "expected_attr"]
        self.assertEqual(
            expected_attr,
            utils.get_nested_attr(containing_obj, existing_attr_path)
        )

        missing_attrs_pathes = [
            ["missing_attr", "expected_attr"],
            ["intermediate_attr", "missing_attr"],
        ]
        for attr_path in missing_attrs_pathes:
            self.assertIsNone(
                utils.get_nested_attr(containing_obj, attr_path)
            )

    def test_get_version_info(self):
        self.assertIsNone(utils.get_version_info(None))
        self.env.create()
        cluster = self.env.clusters[0]
        version_info = utils.get_version_info(cluster)
        self.assertEqual(
            set(('openstack_os', 'openstack_name', 'openstack_version',
                 'fuel_version')),
            set(version_info.keys())
        )
