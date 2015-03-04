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

import re

from nailgun.test import base

from nailgun.api import reverse
from nailgun.api.v1 import urls


def get_params_from_url(url_re):
    param_re = re.compile('\(\?P<(.*?)>.*?\)')
    return param_re.findall(url_re)


def reverse_old(name, kwargs=None):
    urldict = dict(zip(urls.urls[1::2], urls.urls[::2]))
    url = urldict[name]
    urlregex = re.compile(url)
    for kwarg in urlregex.groupindex:
        if kwarg not in kwargs:
            raise KeyError("Invalid argument specified")
        url = re.sub(
            r"\(\?P<{0}>[^)]+\)".format(kwarg),
            str(kwargs[kwarg]),
            url,
            1
        )
    url = re.sub(r"\??\$", "", url)
    return "/api" + url


class TestSameUrls(base.BaseUnitTest):
    """Make sure that URLs before and after Pecan migration haven't changed.
    """
    def setUp(self):
        self.url_tuples = zip(
            urls.original_urls[1::2],
            urls.original_urls[::2]
        )

    def test_same_urls(self):
        for klass, url_re in self.url_tuples:
            if not isinstance(klass, basestring):
                continue

            params = get_params_from_url(url_re)
            param_values = dict(zip(params, range(10)))

            url = reverse(klass, kwargs=param_values)
            url_old = reverse_old(klass, kwargs=param_values)

            self.assertEqual(url.rstrip('/'), url_old.rstrip('/'))
