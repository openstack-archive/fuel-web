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
import StringIO
import sys

import mock
import unittest2

from fuel_package_updates import fuel_package_updates as fpu


def make_release(**overrides):
    release = {
        'id': 2,
        'name': 'Kilo on Ubuntu 14.04.1',
        'operating_system': 'Ubunt',
        'version': '2015.1.0-7.0',
        'is_deployable': True,
        'state': 'available',
        'attributes_metadata': {},
        'can_update_from_versions': [],
        'description': 'robust, enterprise-grade OpenStack deployment.',
        'modes_metadata': {},
        'roles_metadata': {},
        'vmware_attributes_metadata': {},
        'wizard_metadata': {},
    }
    release.update(overrides)
    return release


class CCStringIO(StringIO.StringIO):
    """A "carbon copy" StringIO.

    It's capable of multiplexing its writes to other buffer objects.

    Taken from fabric.tests.mock_streams.CarbonCopy
    """

    def __init__(self, buffer='', writers=None):
        """Init CCStringIO

        If ``writers`` is given and is a file-like object or an
        iterable of same, it/they will be written to whenever this
        StringIO instance is written to.
        """
        StringIO.StringIO.__init__(self, buffer)
        if writers is None:
            writers = []
        elif hasattr(writers, 'write'):
            writers = [writers]
        self.writers = writers

    def write(self, s):
        # unfortunately, fabric writes into StringIO both so-called
        # bytestrings and unicode strings. obviously, bytestrings may
        # contain non-ascii symbols. that leads to type-conversion
        # issue when we use string's join (inside getvalue()) with
        # a list of both unicodes and bytestrings. in order to avoid
        # this issue we should convert all input unicode strings into
        # utf-8 bytestrings (let's assume that slaves encoding is utf-8
        # too so we won't have encoding mess in the output file).
        if isinstance(s, unicode):
            s = s.encode('utf-8')

        StringIO.StringIO.write(self, s)
        for writer in self.writers:
            writer.write(s)


def MockedStdout():
    """Factory for CCStringIO with sys.stdout proxy."""
    return CCStringIO(writers=[sys.__stdout__])


def mock_stdout():
    """Returns mock of sys.stdout with proxy to actual sys.stdout."""
    return mock.patch('sys.stdout', new=MockedStdout())


class BaseCliTestCase(unittest2.TestCase):

    def execute(self, *cli_args):
        cli_args = list(cli_args)
        fpu.main(cli_args)
