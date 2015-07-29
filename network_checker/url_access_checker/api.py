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

import json
import socket

import requests

import url_access_checker.errors as errors


def check_urls(urls, proxies=None):
    responses = map(lambda u: _get_response_tuple(u, proxies=proxies), urls)
    failed_responses = filter(lambda x: x[0], responses)

    if failed_responses:
        raise errors.UrlNotAvailable(json.dumps(
            {'failed_urls': map(lambda r: r[1], failed_responses)}))
    else:
        return True


def _get_response_tuple(url, proxies=None):
    """Return a tuple which contains a result of url test

    Arguments:
    url -- a string containing url for testing

    Result tuple content:
        result[0] -- boolean value, True if the url is deemed failed
        result[1] -- unchange url argument
    """
    try:
        # requests seems to correctly handle various corner cases:
        # proxies=None or proxies={} mean 'use the default' rather than
        # "don't use proxy". To force a direct connection one should pass
        # proxies={'http': None}.
        response = requests.get(url, proxies=proxies, timeout=(20, 60))
        return (response.status_code != 200, url)
    except (requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.HTTPError,
            requests.exceptions.ProxyError,
            ValueError,
            socket.timeout):
        return (True, url)
