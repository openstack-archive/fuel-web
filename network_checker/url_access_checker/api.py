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
import os
import socket

import requests

import url_access_checker.errors as errors


FILE_PREFIX = 'file://'


def check_urls(urls, proxies=None, timeout=60):
    """Checks a set of urls to see if they are valid

    Url is valid if
    - it returns 200 upon requesting it with http (if it doesn't specify
    protocol as "file")
    - it is an existing file or directory (if the protocol used in url is
    "file")

    Arguments:
    urls -- an iterable containing urls for testing
    proxies -- proxy servers to use for the request
    timeout -- the max time to wait for a response, default 60 seconds
    """
    responses = map(lambda u: _get_response_tuple(
        u, proxies=proxies, timeout=timeout), urls)
    failed_responses = filter(lambda x: x[0], responses)

    if failed_responses:
        raise errors.UrlNotAvailable(json.dumps(
            {'failed_urls': map(lambda r: r[1], failed_responses)}))
    else:
        return True


def _get_response_tuple(url, proxies=None, timeout=60):
    """Return a tuple which contains a result of url test

    Arguments:
    url -- a string containing url for testing, can be local file
    proxies -- proxy servers to use for the request
    timeout -- the max time to wait for a response, default 60 seconds

    Result tuple content:
        result[0] -- boolean value, True if the url is deemed failed
        result[1] -- unchange url argument
    """

    if url.startswith(FILE_PREFIX):
        return _get_file_existence_tuple(url)
    else:
        return _get_http_response_tuple(url, proxies, timeout)


def _get_file_existence_tuple(url):
    path = url[len(FILE_PREFIX):]
    return (not os.path.exists(path), url)


def _get_http_response_tuple(url, proxies=None, timeout=60):
    try:
        # requests seems to correctly handle various corner cases:
        # proxies=None or proxies={} mean 'use the default' rather than
        # "don't use proxy". To force a direct connection one should pass
        # proxies={'http': None}.
        # Setting the timeout for requests.get(...) sets max request time. We
        # want to set a value to prevent this process from hanging as the
        # default timeout is None which can lead to bad things when processes
        # never exit. LP#1478138
        response = requests.get(url, proxies=proxies, timeout=timeout)
        return (response.status_code != 200, url)
    except (requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.HTTPError,
            requests.exceptions.ProxyError,
            ValueError,
            socket.timeout):
        return (True, url)
