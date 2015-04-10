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

import logging
import subprocess
import sys

try:
    from collections import OrderedDict
except Exception:
    # python 2.6 or earlier use backport
    from ordereddict import OrderedDict

from fuel_package_updates.settings import SETTINGS

logger = logging.getLogger(__name__)


def exec_cmd(cmd):
    logger.debug('Execute command "%s"', cmd)
    child = subprocess.Popen(
        cmd, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=True)

    logger.debug('Stdout and stderr of command "%s":', cmd)
    for line in child.stdout:
        logger.debug(line.rstrip())

    return _wait_and_check_exit_code(cmd, child)


def _wait_and_check_exit_code(cmd, child):
    child.wait()
    exit_code = child.returncode
    logger.debug('Command "%s" was executed', cmd)
    return exit_code


def repo_merge(list_a, list_b):
    """Merges two lists of repositories (dicts).

    'list_b' replaces records from 'list_a' basing on repos names.

    :param list_a: list of dicts in format:
                [{
                    "type": "deb",
                    "name": "mos-security",
                    "uri": "some/uri",
                 },
                ...
                ]
    :param list_b: list of dicts - format the same as in 'list_a'
    :return: merged list of dicts
    """
    to_merge = list_a + list_b
    primary_repos = sorted(filter(
        lambda x:
        x['name'].startswith('ubuntu')
        or x['name'].startswith(SETTINGS.ubuntu_codename),
        to_merge))

    result = OrderedDict()
    for repo in primary_repos:
        result[repo['name']] = None

    for repo in to_merge:
        name = repo['name']
        if repo.get('delete') is True:
            result.pop(name, None)
        else:
            result[name] = repo

    return result.values()


def exit_with_error(msg, code=1):
    logging.error("\n{0}".format(reindent(msg, spaces=4)))
    sys.exit(code)


def reindent(s, spaces=10):
    return '\n'.join((spaces * ' ') + line for line in s.split('\n'))
