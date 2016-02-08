# -*- coding: utf-8 -*-

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

import mock

from nailgun.api.v1.urls import get_all_urls
from nailgun.api.v1.urls import get_extensions_urls

from nailgun.test.base import BaseTestCase


class FakeHandler(object):
    pass


class TestUrls(BaseTestCase):

    @mock.patch('nailgun.api.v1.urls.get_extensions_urls')
    @mock.patch('nailgun.api.v1.urls.get_feature_groups_urls')
    def test_get_all_urls(self, mock_get_feature_groups_urls,
                          mock_get_extensions_urls):
        mock_get_extensions_urls.return_value = {
            'urls': (r'/ext/url/', 'FakeHandler'),
            'handlers': [{
                'class': FakeHandler,
                'name': 'FakeHandler'}]}
        mock_get_feature_groups_urls.return_value = ['/advanced/url/']
        result = get_all_urls()
        # Urls
        all_urls = result[0]
        # Variables
        all_vars = result[1]

        self.assertIn('/ext/url/', all_urls[-2])
        self.assertIn('/advanced/url/', all_urls)
        self.assertIn('FakeHandler', all_urls[-1])

        self.assertEqual(all_vars['FakeHandler'], FakeHandler)

    @mock.patch('nailgun.api.v1.urls.get_all_extensions')
    def test_get_extensions_urls(self, mock_get_all_extensions):
        extension = mock.MagicMock(urls=[
            {'uri': '/ext/uri', 'handler': FakeHandler}])
        mock_get_all_extensions.return_value = [extension]

        self.assertEqual(
            get_extensions_urls(),
            {'urls': ['/ext/uri', 'FakeHandler'],
             'handlers': [{'class': FakeHandler, 'name': 'FakeHandler'}]})

    @mock.patch.dict('nailgun.api.v1.urls.settings.VERSION',
                     {'feature_groups': []})
    def test_get_feature_urls(self):

        result = get_all_urls()
        # Urls
        all_urls = result[0]

        self.assertNotIn('/clusters/(?P<cluster_id>\d+)/spawn_vms/?$',
                         all_urls)
