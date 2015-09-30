# -*- coding: utf-8 -*-

# Copyright 2014 Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from six import add_metaclass

from nailgun.test.base import BaseIntegrationTest
from nailgun.utils import reverse


class BaseTestRemovedResources(BaseIntegrationTest):
    def assert_resp_correct(self, resp):
        self.assertEqual(resp.status_code, 410)
        self.assertEqual(resp.json_body["message"], self.message)

    def setUp(self):
        super(BaseTestRemovedResources, self).setUp()

        self.message = u"Removed in Fuel version 5.1"
        self.kwargs = {
            'headers': self.default_headers,
            'params': {'fa': 'ke', 'pa': 'ra', 'm': 5},
            'expect_errors': True
        }


class BaseTestDataProviderMeta(type):
    def __new__(meta, classname, bases, class_dict):
        def create_test_method(handler, method):
            def test_method(self):
                if method == 'head':
                    self.kwargs.pop('params')
                r = getattr(self.app, method)(handler, **self.kwargs)
                self.assert_resp_correct(r)

            return test_method

        for handler in meta.handlers:
            for method in meta.methods:
                suffix = handler.strip('/').lower().replace('/', '_')
                name = 'test_removed_{0}_{1}'.format(method, suffix)
                class_dict[name] = create_test_method(handler, method)

        return type.__new__(meta, classname, bases, class_dict)


class RemovedResourcesMeta(BaseTestDataProviderMeta):
    handlers = (
        reverse('RemovedIn51RedHatAccountHandler'),
        reverse('RemovedIn51RedHatSetupHandler')
    )
    methods = ('get', 'head', 'post', 'put', 'delete')


@add_metaclass(RemovedResourcesMeta)
class TestRemovedResources(BaseTestRemovedResources):
    pass


class RemovedIn51HandlerMeta(BaseTestDataProviderMeta):
    handlers = ('/api/v1/test/res/',)
    methods = ('get', 'head', 'post', 'put', 'delete')
