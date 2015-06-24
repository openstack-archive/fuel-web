# -*- coding: utf-8 -*-

#    Copyright 2013 Mirantis, Inc.
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

from mock import mock_open
from mock import patch
import os
import tempfile

import requests

from nailgun.test import base
from nailgun.utils import camel_to_snake_case
from nailgun.utils import compact
from nailgun.utils import dict_merge
from nailgun.utils import flatten
from nailgun.utils import get_fuel_release_versions
from nailgun.utils import grouper
from nailgun.utils import traverse

from nailgun.utils.debian import get_apt_preferences_line
from nailgun.utils.debian import get_release_file
from nailgun.utils.debian import parse_release_file


class TestUtils(base.BaseIntegrationTest):

    def test_dict_merge(self):
        custom = {"coord": [10, 10],
                  "pass": "qwerty",
                  "dict": {"body": "solid",
                           "color": "black",
                           "dict": {"stuff": "hz"}}}
        common = {"parent": None,
                  "dict": {"transparency": 100,
                           "dict": {"another_stuff": "hz"}}}
        result = dict_merge(custom, common)
        self.assertEqual(result, {"coord": [10, 10],
                                  "parent": None,
                                  "pass": "qwerty",
                                  "dict": {"body": "solid",
                                           "color": "black",
                                           "transparency": 100,
                                           "dict": {"stuff": "hz",
                                                    "another_stuff": "hz"}}})

    @patch('nailgun.utils.glob.glob', return_value=['test.yaml'])
    @patch('__builtin__.open', mock_open(read_data='test_data'))
    def test_get_release_versions(self, _):
        versions = get_fuel_release_versions(None)
        self.assertDictEqual({'test': 'test_data'}, versions)

    def test_get_release_versions_empty_file(self):
        with tempfile.NamedTemporaryFile() as tf:
            versions = get_fuel_release_versions(tf.name)
            self.assertDictEqual({os.path.basename(tf.name): None}, versions)

    def test_get_release_no_file(self):
        with tempfile.NamedTemporaryFile() as tf:
            file_path = tf.name
        self.assertFalse(os.path.exists(file_path))
        versions = get_fuel_release_versions(file_path)
        self.assertDictEqual({}, versions)

    def test_camel_case_to_snake_case(self):
        self.assertTrue(
            camel_to_snake_case('TestCase') == 'test_case')
        self.assertTrue(
            camel_to_snake_case('TTestCase') == 't_test_case')

    def test_compact(self):
        self.assertListEqual(
            compact([1, '', 5, False, None, False, 'test']),
            [1, 5, 'test'])

    def test_flatten(self):
        self.assertListEqual(
            flatten([7, 5, [3, [4, 5], 1], 2]),
            [7, 5, 3, [4, 5], 1, 2])

    def test_grouper(self):
        self.assertEqual(
            list(grouper([0, 1, 2, 3], 2)), [(0, 1), (2, 3)])

        self.assertEqual(
            list(grouper([0, 1, 2, 3, 4, 5], 3)), [(0, 1, 2), (3, 4, 5)])

        self.assertEqual(
            list(grouper([0, 1, 2, 3, 4], 3)), [(0, 1, 2), (3, 4, None)])

        self.assertEqual(
            list(grouper([0, 1, 2, 3, 4], 3, 'x')), [(0, 1, 2), (3, 4, 'x')])


class TestTraverse(base.BaseUnitTest):

    class TestGenerator(object):
        @classmethod
        def test(cls, arg=None):
            return 'testvalue'

    data = {
        'foo': {
            'generator': 'test',
        },
        'bar': 'test {a} string',
        'baz': 42,
        'regex': {
            'source': 'test {a} string',
            'error': 'an {a} error'
        },

        'list': [
            {
                'x': 'a {a} a',
            },
            {
                'y': 'b 42 b',
            }
        ]
    }

    def test_wo_formatting_context(self):
        result = traverse(self.data, self.TestGenerator)

        self.assertEqual(result, {
            'foo': 'testvalue',
            'bar': 'test {a} string',
            'baz': 42,
            'regex': {
                'source': 'test {a} string',
                'error': 'an {a} error'
            },
            'list': [
                {
                    'x': 'a {a} a',
                },
                {
                    'y': 'b 42 b',
                }
            ]})

    def test_w_formatting_context(self):
        result = traverse(self.data, self.TestGenerator, {'a': 13})

        self.assertEqual(result, {
            'foo': 'testvalue',
            'bar': 'test 13 string',
            'baz': 42,
            'regex': {
                'source': 'test {a} string',
                'error': 'an {a} error'
            },
            'list': [
                {
                    'x': 'a 13 a',
                },
                {
                    'y': 'b 42 b',
                }
            ]})


class TestGetDebianReleaseFile(base.BaseUnitTest):

    @patch('nailgun.utils.debian.requests.get')
    def test_normal_ubuntu_repo(self, m_get):
        get_release_file({
            'name': 'myrepo',
            'uri': 'http://some-uri.com/path',
            'suite': 'mysuite',
            'section': 'main university',
        })
        m_get.assert_called_with(
            'http://some-uri.com/path/dists/mysuite/Release')

    @patch('nailgun.utils.debian.requests.get')
    def test_flat_ubuntu_repo(self, m_get):
        testcases = [
            # (suite, uri)
            ('/', 'http://some-uri.com/deb/Release'),
            ('/path', 'http://some-uri.com/deb/path/Release'),
            ('path', 'http://some-uri.com/deb/path/Release'),
        ]

        for suite, uri in testcases:
            get_release_file({
                'name': 'myrepo',
                'uri': 'http://some-uri.com/deb',
                'suite': suite,
                'section': '',
            })
            m_get.assert_called_with(uri)

    @patch('nailgun.utils.debian.requests.get')
    def test_do_not_silence_http_errors(self, m_get):
        r = requests.Response()
        r.status_code = 404
        m_get.return_value = r

        self.assertRaises(requests.exceptions.HTTPError, get_release_file, {
            'name': 'myrepo',
            'uri': 'http://some-uri.com/path',
            'suite': 'mysuite',
            'section': 'main university',
        })

    @patch('nailgun.utils.debian.requests.get')
    def test_do_not_retry_on_404(self, m_get):
        r = requests.Response()
        r.status_code = 404
        m_get.return_value = r

        self.assertRaises(requests.exceptions.HTTPError, get_release_file, {
            'name': 'myrepo',
            'uri': 'http://some-uri.com/path',
            'suite': 'mysuite',
            'section': 'main university',
        }, retries=3)
        self.assertEqual(m_get.call_count, 1)

    @patch('nailgun.utils.debian.requests.get')
    def test_do_retry_on_error(self, m_get):
        r = requests.Response()
        r.status_code = 500
        m_get.return_value = r

        self.assertRaises(requests.exceptions.HTTPError, get_release_file, {
            'name': 'myrepo',
            'uri': 'http://some-uri.com/path',
            'suite': 'mysuite',
            'section': 'main university',
        }, retries=3)
        self.assertEqual(m_get.call_count, 3)

    @patch('nailgun.utils.debian.requests.get')
    def test_returns_content_if_http_ok(self, m_get):
        r = requests.Response()
        r._content = 'content'
        r.status_code = 200
        m_get.return_value = r

        content = get_release_file({
            'name': 'myrepo',
            'uri': 'http://some-uri.com/path',
            'suite': 'mysuite',
            'section': 'main university',
        })
        self.assertEqual(content, 'content')


class TestParseDebianReleaseFile(base.BaseUnitTest):

    _deb_release_info = '''
      Origin: TestOrigin
      Label: TestLabel
      Archive: test-archive
      Codename: testcodename
      Date: Thu, 08 May 2014 14:19:09 UTC
      Architectures: amd64 i386
      Components: main restricted universe multiverse
      Description: Test Description
      MD5Sum:
       ead1cbf42ed119c50bf3aab28b5b6351         934 main/binary-amd64/Packages
       52d605b4217be64f461751f233dd9a8f          96 main/binary-amd64/Release
      SHA1:
       28c4460e3aaf1b93f11911fdc4ff23c28809af89 934 main/binary-amd64/Packages
       d03d716bceaba35f91726c096e2a9a8c23ccc766  96 main/binary-amd64/Release
    '''

    def test_parse(self):
        deb_release = parse_release_file(self._deb_release_info)

        self.assertEqual(deb_release, {
            'Origin': 'TestOrigin',
            'Label': 'TestLabel',
            'Archive': 'test-archive',
            'Codename': 'testcodename',
            'Date': 'Thu, 08 May 2014 14:19:09 UTC',
            'Architectures': 'amd64 i386',
            'Components': 'main restricted universe multiverse',
            'Description': 'Test Description',
            'MD5Sum': [
                {
                    'md5sum': 'ead1cbf42ed119c50bf3aab28b5b6351',
                    'size': '934',
                    'name': 'main/binary-amd64/Packages',
                },
                {
                    'md5sum': '52d605b4217be64f461751f233dd9a8f',
                    'size': '96',
                    'name': 'main/binary-amd64/Release',
                }
            ],
            'SHA1': [
                {
                    'sha1': '28c4460e3aaf1b93f11911fdc4ff23c28809af89',
                    'size': '934',
                    'name': 'main/binary-amd64/Packages',
                },
                {
                    'sha1': 'd03d716bceaba35f91726c096e2a9a8c23ccc766',
                    'size': '96',
                    'name': 'main/binary-amd64/Release',
                }
            ],
        })


class TestGetAptPreferencesLine(base.BaseUnitTest):

    _deb_release = {
        'Origin': 'TestOrigin',
        'Label': 'TestLabel',
        'Archive': 'test-archive',
        'Version': '42.42',
        'Codename': 'testcodename',
        'Date': 'Thu, 08 May 2014 14:19:09 UTC',
        'Architectures': 'amd64 i386',
        'Components': 'main restricted universe multiverse',
        'Description': 'Test Description',
    }

    def test_all_rules(self):
        pin = get_apt_preferences_line(self._deb_release)
        self.assertItemsEqual(pin.split(','), [
            'o=TestOrigin',
            'l=TestLabel',
            'a=test-archive',
            'v=42.42',
            'n=testcodename',
        ])

    def test_not_all_rules(self):
        deb_release = self._deb_release.copy()

        del deb_release['Codename']
        del deb_release['Label']
        del deb_release['Version']

        pin = get_apt_preferences_line(deb_release)
        self.assertItemsEqual(pin.split(','), [
            'o=TestOrigin',
            'a=test-archive',
        ])

    def test_suite_is_synonym_for_archive(self):
        deb_release = self._deb_release.copy()
        deb_release['Suite'] = 'test-suite'
        del deb_release['Archive']

        pin = get_apt_preferences_line(deb_release)
        conditions = pin.split(',')

        self.assertIn('a=test-suite', conditions)
