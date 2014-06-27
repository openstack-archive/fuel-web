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

import json
import logging
import os
import re
import shutil
import subprocess
import time
import urllib2

from copy import deepcopy

from mako.template import Template
import yaml

from fuel_upgrade import errors

logger = logging.getLogger(__name__)


def exec_cmd(cmd):
    """Execute command with logging.
    Ouput of stdout and stderr will be written
    in log.

    :param cmd: shell command
    """
    logger.debug(u'Execute command "{0}"'.format(cmd))
    child = subprocess.Popen(
        cmd, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=True)

    logger.debug(u'Stdout and stderr of command "{0}":'.format(cmd))
    for line in child.stdout:
        logger.debug(line.rstrip())

    _wait_and_check_exit_code(cmd, child)


def exec_cmd_iterator(cmd):
    """Execute command with logging.

    :param cmd: shell command
    :returns: generator where yeach item
              is line from stdout
    """
    logger.debug(u'Execute command "{0}"'.format(cmd))
    child = subprocess.Popen(
        cmd, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True)

    logger.debug(u'Stdout and stderr of command "{0}":'.format(cmd))
    for line in child.stdout:
        logger.debug(line.rstrip())
        yield line

    _wait_and_check_exit_code(cmd, child)


def _wait_and_check_exit_code(cmd, child):
    """Wait for child and check it's exit code

    :param cmd: command
    :param child: object which returned by subprocess.Popen
    :raises: ExecutedErrorNonZeroExitCode
    """
    child.wait()
    exit_code = child.returncode

    if exit_code != 0:
        raise errors.ExecutedErrorNonZeroExitCode(
            u'Shell command executed with "{0}" '
            'exit code: {1} '.format(exit_code, cmd))

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

    return json.loads(response_data), response_code


def topological_sorting(dep_graph):
    """Implementation of topological sorting algorithm
    http://en.wikipedia.org/wiki/Topological_sorting

    :param dep_graph: graph of dependencies, where key is
                      a node and value is a list of dependencies
    :returns: list of nodes
    :raises CyclicDependencies:
    """
    sorted_nodes = []
    graph = deepcopy(dep_graph)

    while graph:
        cyclic = True
        for node, dependencies in sorted(graph.items(), key=lambda n: n[0]):
            for dependency in dependencies:
                if dependency in graph:
                    break
            else:
                cyclic = False
                del graph[node]
                sorted_nodes.append(node)

        if cyclic:
            raise errors.CyclicDependenciesError(
                u'Cyclic dependencies error {0}'.format(graph))

    return sorted_nodes


def create_dir_if_not_exists(dir_path):
    """Creates directory if it doesn't exist

    :param dir_path: directory path
    """
    if not os.path.isdir(dir_path):
        os.makedirs(dir_path)


def render_template_to_file(src, dst, params):
    """Render mako template and write it to specified file

    :param src: path to template
    :param dst: path where rendered template will be saved
    """
    logger.debug('Render template from {0} to {1} with params: {2}'.format(
        src, dst, params))
    with open(src, 'r') as f:
        template_cfg = f.read()

    with open(dst, 'w') as f:
        rendered_cfg = Template(template_cfg).render(**params)
        f.write(rendered_cfg)


def wait_for_true(check, timeout=60, interval=0.5):
    """Execute command with retries

    :param check: callable object
    :param timeout: timeout
    :returns: result of call method

    :raises TimeoutError:
    """
    start_time = time.time()

    while True:
        result = check()
        if result:
            return result
        if time.time() - start_time > timeout:
            raise errors.TimeoutError(
                'Failed to execute '
                'command with timeout {0}'.format(timeout))
        time.sleep(interval)


def symlink(from_path, to_path):
    """Create symlink, and remove old if it exists

    :param from_path: symlink from
    :param to_path: symlink to
    """
    logger.debug(
        u'Create symlink from "{0}" to "{1}"'.format(from_path, to_path))

    remove_if_exists(to_path)
    os.symlink(from_path, to_path)


def remove_if_exists(path):
    """Removes files if it exists

    :param path: path to file for removal
    """
    if os.path.exists(path):
        logger.debug(u'Remove file "{0}"'.format(path))
        os.remove(path)


def file_contains_lines(file_path, patterns):
    """Checks if file contains lines
    which described by patterns

    :param file_path: path to file
    :param patterns: list of strings
    :returns: True if file matches all patterns
              False if file doesn't match one or more patterns
    """
    logger.debug(
        u'Check if file "{0}" matches to pattern "{1}"'.format(
            file_path, patterns))

    regexps = [re.compile(pattern) for pattern in patterns]

    with open(file_path, 'r') as f:
        for line in f:
            for i, regexp in enumerate(regexps):
                result = regexp.search(line)
                if result:
                    del regexps[i]

    if regexps:
        logger.warn('Cannot find lines {0} in file {1}'.format(
            regexps, file_path))
        return False

    return True


def copy(from_path, to_path):
    """Copy file, override if exists

    :param from_path: src path
    :param to_path: dst path
    """
    logger.debug(u'Copy file from {0} to {1}'.format(from_path, to_path))
    shutil.copy(from_path, to_path)


def copytree(source, destination, overwrite=True):
    """Copy a given source directory to destination folder.
    """
    logger.debug(u'Copy folder from %s to %s', source, destination)

    if overwrite and os.path.exists(destination):
        shutil.rmtree(destination)
    shutil.copytree(source, destination, symlinks=True)


def rmtree(source, ignore_errors=True):
    logger.debug(u'Removing %s', source)
    shutil.rmtree(source, ignore_errors=ignore_errors)


def dict_merge(a, b):
    '''recursively merges dict's. not just simple a['key'] = b['key'], if
    both a and bhave a key who's value is a dict then dict_merge is called
    on both values and the result stored in the returned dictionary.
    '''
    if not isinstance(b, dict):
        return deepcopy(b)
    result = deepcopy(a)
    for k, v in b.iteritems():
        if k in result and isinstance(result[k], dict):
            result[k] = dict_merge(result[k], v)
        else:
            result[k] = deepcopy(v)
    return result


def load_fixture(fileobj, loader=None):
    # a key that's used to mark some item as abstract
    pk_key = 'pk'

    # a key that's used to tell some item inherit data
    # from an abstract one
    inherit_key = 'extend'

    # a list of supported loaders; the loader should be a func
    # that receives a file-like object
    supported_loaders = {
        '.json': json.load,
        '.yaml': yaml.load,
        '.yml': yaml.load,
    }

    def extend(obj):
        if inherit_key in obj:
            obj[inherit_key] = extend(obj[inherit_key])
        return dict_merge(obj.get(inherit_key, {}), obj)

    # try to get loader from a given fixture if loader is None
    if loader is None:
        _, ext = os.path.splitext(fileobj.name)
        loader = supported_loaders[ext]
    fixture = loader(fileobj)

    # render fixture
    fixture = filter(lambda obj: obj.get(pk_key) is not None, fixture)
    for i in range(0, len(fixture)):
        fixture[i] = extend(fixture[i])
        fixture[i].pop(inherit_key, None)

    return [f['fields'] for f in fixture]
