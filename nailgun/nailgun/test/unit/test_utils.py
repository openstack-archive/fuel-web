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

import mock

import requests

from nailgun.test import base
from nailgun.utils import camel_to_snake_case
from nailgun.utils import compact
from nailgun.utils import dict_merge
from nailgun.utils import flatten
from nailgun.utils import get_lines
from nailgun.utils import grouper
from nailgun.utils import text_format_safe
from nailgun.utils import traverse

from nailgun.utils.debian import get_apt_preferences_line
from nailgun.utils.debian import get_release_file
from nailgun.utils.debian import parse_release_file

from nailgun.utils.fake_generator import FakeNodesGenerator


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

    def test_get_lines(self):
        empty = ""
        empty_multiline = "\n\n\n"
        non_empty = "abc\nfoo\nbar"
        mixed = "abc\n\nfoo\n\n\nbar"

        self.assertEqual(get_lines(empty), [])

        self.assertEqual(get_lines(empty_multiline), [])

        self.assertEqual(get_lines(non_empty), ['abc', 'foo', 'bar'])

        self.assertEqual(get_lines(mixed), ['abc', 'foo', 'bar'])


class TestTraverse(base.BaseUnitTest):

    class TestGenerator(object):
        @classmethod
        def test(cls, arg=None):
            return 'testvalue'

        @classmethod
        def evaluate(cls, func, arg=None):
            return getattr(cls, func)(arg)

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
        result = traverse(
            self.data,
            keywords={'generator': self.TestGenerator.evaluate}
        )

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
        result = traverse(
            self.data,
            formatter_context={'a': 13},
            keywords={'generator': self.TestGenerator.evaluate}
        )

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

    def test_formatter_returns_informative_error(self):
        with self.assertRaisesRegexp(ValueError, '{a}'):
            traverse(
                self.data,
                formatter_context={'b': 13},
                keywords={'generator': self.TestGenerator.evaluate}
            )

    def test_w_safe_formatting_context(self):
        data = self.data.copy()
        data['bar'] = 'test {b} value'
        result = traverse(
            data, text_format_safe, {'a': 13},
            keywords={'generator': self.TestGenerator.evaluate}
        )

        self.assertEqual(result, {
            'foo': 'testvalue',
            'bar': 'test {b} value',
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

    def test_custom_keywords(self):
        data = {
            'key1': {'exp1': 'name1', 'exp1_arg': 'arg1'},
            'key2': {'exp2': 'name2'},
        }
        generator1 = mock.MagicMock(return_value='val1')
        generator2 = mock.MagicMock(return_value='val2')
        result = traverse(data, keywords={
            'exp1': generator1,
            'exp2': generator2
        })
        self.assertEqual({'key1': 'val1', 'key2': 'val2'}, result)
        generator1.assert_called_once_with('name1', 'arg1')
        generator2.assert_called_once_with('name2')


class TestGetDebianReleaseFile(base.BaseUnitTest):

    @mock.patch('nailgun.utils.debian.requests.get')
    def test_normal_ubuntu_repo(self, m_get):
        get_release_file({
            'name': 'myrepo',
            'uri': 'http://some-uri.com/path',
            'suite': 'mysuite',
            'section': 'main university',
        })
        m_get.assert_called_with(
            'http://some-uri.com/path/dists/mysuite/Release')

    @mock.patch('nailgun.utils.debian.requests.get')
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

    @mock.patch('nailgun.utils.debian.requests.get')
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

    @mock.patch('nailgun.utils.debian.requests.get')
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

    @mock.patch('nailgun.utils.debian.requests.get')
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

    @mock.patch('nailgun.utils.debian.requests.get')
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


class TestFakeNodeGenerator(base.BaseUnitTest):
    def setUp(self):
        self.generator = FakeNodesGenerator()

    def test_generate_fake_nodes_with_total_count(self):
        total_nodes_count = 8
        generated_nodes = self.generator.generate_fake_nodes(total_nodes_count)
        self.assertEqual(total_nodes_count, len(generated_nodes))

    def test_generate_fake_nodes_with_error_offline_nodes(self):
        total_nodes_count = 7
        error_nodes_count = 2
        offline_nodes_count = 1
        offloading_ifaces_nodes_count = 3

        generated_nodes = self.generator.generate_fake_nodes(
            total_nodes_count, error_nodes_count, offline_nodes_count,
            offloading_ifaces_nodes_count
        )
        self.assertEqual(total_nodes_count, len(generated_nodes))
        generated_error_nodes = [n for n in generated_nodes if
                                 n['fields']['status'] == 'error']
        self.assertEqual(error_nodes_count, len(generated_error_nodes))
        generated_offline_nodes = [n for n in generated_nodes if
                                   not n['fields']['online']]
        self.assertEqual(offline_nodes_count, len(generated_offline_nodes))

        offloading_ifaces_nodes = [
            n for n in generated_nodes if
            n['fields']['meta']['interfaces'][0].get('offloading_modes')
        ]
        self.assertEqual(offloading_ifaces_nodes_count,
                         len(offloading_ifaces_nodes))

    def test_generate_fake_nodes_with_wrong_params(self):
        total_nodes_count = 4
        error_nodes_count = 2
        offline_nodes_count = 5
        generated_nodes = self.generator.generate_fake_nodes(
            total_nodes_count, error_nodes_count, offline_nodes_count)
        self.assertEqual(total_nodes_count, len(generated_nodes))

        actual_error_nodes = len(
            [n for n in generated_nodes if n['fields']['status'] == 'error'])
        actual_offline_nodes = len(
            [n for n in generated_nodes if not n['fields']['online']])
        self.assertTrue(
            total_nodes_count >= actual_error_nodes + actual_offline_nodes)

    def test_generate_fake_node_common_structure(self):
        pk = 123
        sample_node_fields = {
            'status': 'discover',
            'name': 'Supermicro X9DRW',
            'hostname': 'node-1',
            'ip': '172.18.67.168',
            'online': True,
            'labels': {},
            'pending_addition': False,
            'platform_name': 'X9DRW',
            'mac': '00:25:90:6a:b1:10',
            'timestamp': '',
            'progress': 0,
            'pending_deletion': False,
            'os_platform': 'ubuntu',
            'manufacturer': 'Supermicro',
            'meta': {
                'cpu': {},
                'interfaces': [],
                'disks': [],
                'system': {},
                'memory': []
            }
        }
        generated_node = self.generator.generate_fake_node(pk)
        self.assertEqual(generated_node.get('pk'), pk)
        self.assertEqual(generated_node.get('model'), 'nailgun.node')
        generated_node_fields = generated_node.get('fields', {})
        self.assertItemsEqual(sample_node_fields.keys(),
                              generated_node_fields.keys())
        self.assertItemsEqual(sample_node_fields['meta'].keys(),
                              generated_node_fields.get('meta', {}).keys())
        self.assertFalse(generated_node_fields.get('pending_deletion'))
        self.assertFalse(generated_node_fields.get('pending_addition'))
        self.assertEqual(generated_node_fields.get('progress'), 0)

    def test_generate_fake_node_with_params(self):
        pk = 123
        is_online = False

        generated_node = self.generator.generate_fake_node(
            pk, is_online=is_online, use_offload_iface=True)
        self.assertEqual(pk, generated_node.get('pk'))
        generated_node_fields = generated_node.get('fields')
        self.assertEqual(is_online, generated_node_fields.get('online'))
        self.assertEqual('discover', generated_node_fields.get('status'))
        self.assertIn('offloading_modes',
                      generated_node_fields['meta'].get('interfaces')[0])

        pk = 321
        generated_node = self.generator.generate_fake_node(
            pk, is_error=True, use_offload_iface=False)
        self.assertEqual(pk, generated_node.get('pk'))
        generated_node_fields = generated_node.get('fields')
        self.assertTrue(generated_node_fields.get('online'))
        self.assertEqual('error', generated_node_fields.get('status'))
        self.assertNotIn('offloading_modes',
                         generated_node_fields['meta'].get('interfaces')[0])

    def test_generate_fake_node_interface_meta(self):
        generated_node_fields = self.generator.generate_fake_node(1)['fields']
        known_mac = generated_node_fields['mac']
        known_ip = generated_node_fields['ip']
        ifaces = generated_node_fields['meta']['interfaces']
        suitable_ifaces = [
            x['name'] for x in ifaces if
            x.get('ip') == known_ip or x.get('mac') == known_mac
        ]
        self.assertEqual(len(set(suitable_ifaces)), 1)

    def test_generate_fake_node_disk_suffixes(self):
        count = 500
        disk_suffixes = list(self.generator._get_disk_suffixes(count))
        self.assertEqual(len(set(disk_suffixes)), count)
        self.assertEqual(disk_suffixes[27], 'ab')

    def test_generate_disks_meta_with_non_zero_size(self):
        memory_random_side_effect = [
            {
                'model': 'Virtual Floppy0',
                'name': 'sde',
                'disk': 'sde',
                'size': 0
            },
            {
                'model': 'Virtual HDisk0',
                'name': 'sdf',
                'disk': 'sdf',
                'size': 0
            },
            {
                'model': 'TOSHIBA MK1002TS',
                'name': 'sda',
                'disk': 'sda',
                'size': 1000204886016
            }
        ]

        with mock.patch('random.choice',
                        side_effect=memory_random_side_effect) as mock_random:
            disks_meta = self.generator._generate_disks_meta(1)
            self.assertNotEqual(disks_meta[0]['size'], 0)
            self.assertEqual(mock_random.call_count, 3)
