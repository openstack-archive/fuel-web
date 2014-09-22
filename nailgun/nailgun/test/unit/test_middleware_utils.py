#    Copyright 2014 Mirantis, Inc.
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

import re
import six

from nailgun.test.base import TestCase

from nailgun.middleware import utils


class TestUtils(TestCase):

    def test_get_body_from_env(self):
        expected_body = "Hi! I'm test body"
        expected_len = len(expected_body)

        env = {"CONTENT_LENGTH": str(expected_len),
               "wsgi.input": six.StringIO(expected_body)}

        body = utils.get_body_from_env(env)

        self.assertTrue(env.get("wsgi.input"))
        self.assertEqual(
            len(env["wsgi.input"].read(int(env["CONTENT_LENGTH"]))),
            expected_len
        )
        self.assertEqual(body, expected_body)

        for cl in (None, '', 0):
            env["CONTENT_LENGTH"] = cl
            body = utils.get_body_from_env(env)

            self.assertEqual(body, '')

    def test_compile_mapping_keys(self):
        expected_node_handler = "NodeHandler"
        expected_cluster_handler = "ClusterCollectionHandler"
        mapping = {
            r"/nodes/(?P<obj_id>\d+)/?$": expected_node_handler,
            r"/clusters/?$": expected_cluster_handler
        }

        compiled_mapping = utils.compile_mapping_keys(mapping=mapping)

        def check_match_strings(string_to_match, expected_value,
                                check_not_found=True):
            for matcher, handler_name in six.iteritems(compiled_mapping):
                if matcher.match(string_to_match):
                    self.assertEqual(handler_name, expected_value)
                    break
            else:
                if check_not_found:
                    raise AssertionError("Match not found in compiled mapping")

        test_cases = [
            {"string_to_match": "/nodes/1",
             "expected_value": expected_node_handler},
            {"string_to_match": "/clusters/",
             "expected_value": expected_cluster_handler},
            {"string_to_match": "/settings/",
             "expected_value": "",
             "check_not_found": False},
        ]

        for kw in test_cases:
            check_match_strings(**kw)

    def test_get_group_from_matcher(self):

        def check_group_getter(expected_group_value, kwarg_to_update={}):
            kwargs = {
                "matcher_obj": re.compile(r"/nodes/(?P<obj_id>\d+)/?$"),
                "string_to_match": "/nodes/1",
                "group_name": "obj_id"
            }

            kwargs.update(kwarg_to_update)

            group_value = utils.get_group_from_matcher(**kwargs)
            self.assertEqual(group_value, expected_group_value)

        test_cases = [
            {"expected_group_value": "1"},
            {"expected_group_value": None,
             "kwarg_to_update": {
                 "string_to_match": "/clusters/1"
             }},
            {"expected_group_value": None,
             "kwarg_to_update": {
                 "group_name": "node_id"
             }}
        ]

        for kw in test_cases:
            check_group_getter(**kw)
