# -*- coding: utf-8 -*-

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

import logging
import subprocess
import urllib2

import json

from fuel_upgrade import errors

logger = logging.getLogger(__name__)


def exec_cmd(cmd):
    """Execute command with logging.
    Ouput of stdout and stderr will be written
    in log.

    :param cmd: shell command
    :raises: ExecutedErrorNonZeroExitCode
    """
    logger.debug(u'Execute command "{0}"'.format(cmd))
    child = subprocess.Popen(
        cmd, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=True)

    logger.debug(u'Stdout and stderr of command "{0}":'.format(cmd))
    for line in child.stdout:
        logger.debug(line.rstrip())

    child.wait()
    return_code = child.returncode

    if return_code != 0:
        raise errors.ExecutedErrorNonZeroExitCode(
            u'Shell command executed with "{0}" '
            'exit code: {1} '.format(return_code, cmd))

    logger.debug(u'Command "{0}" successfully executed'.format(cmd))


def get_request(url):
    """Make http get request and deserializer json response

    :param url: url
    :returns list|dict: deserialized response
    """
    logger.debug('GET request to {0}'.format(url))
    response = urllib2.urlopen(url)
    response_data = response.read()
    response_code = response.getcode()
    logger.debug('GET response from {0}, code {1}, data: {2}'.format(
        url, response_code, response_data))

    return json.loads(response_data)


def post_request(url, data, headers=None):
    """Makes an HTTP POST request to a given url.

    :param url: a resource url post to, as a string
    :param data: a data to be posted, as a dict
    :param headers: HTTP headers goind with request, as a dict
    :returns: a deserialized HTTP response and HTTP status code
    """
    request = urllib2.Request(
        url,
        json.dumps(data),
        headers or {}
    )

    try:
        response = urllib2.urlopen(request)
    except urllib2.HTTPError as e:
        return e.message, e.code

    return json.loads(response.read()), response.getcode()


def delete_request(url):
    """Makes an HTTP DELETE request to a given url.

    :param url: a resource url to be deleted, as a string
    """
    request = urllib2.Request(url)
    request.get_method = lambda: 'DELETE'

    response = urllib2.urlopen(request)
    return response.read(), response.getcode()
