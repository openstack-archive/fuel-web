#    Copyright 2016 Mirantis, Inc.
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

import mock
import yaml

from nailgun.test import base
from nailgun import utils


class TestFilesManager(base.BaseTestCase):
    package_version = '1.0.0'

    _test_data_obj = {
        'field1': 'val1',
        'field2': ['val2']
    }
    _test_data_array = ['val1', 'val2']

    _test_text = u"Test\ntext"

    def setUp(self):
        super(TestFilesManager, self).setUp()

    def test_integrity(self):
        formats = ['json', 'yaml', 'txt', 'md']
        fm = utils.FilesManager()
        self.assertItemsEqual(formats, fm.supported_input_formats)
        self.assertItemsEqual(formats, fm.supported_output_formats)

    @mock.patch('nailgun.utils.files_manager.glob.glob')
    def test_load_yaml(self, glob_m):
        open_mock = mock.mock_open(
            read_data=yaml.safe_dump(self._test_data_obj))
        glob_m.return_value = ['/some/path/myfile.yaml']
        with mock.patch(
                'nailgun.utils.files_manager.open',
                open_mock,
                create=True):
            fm = utils.FilesManager()
            result = fm.load('/some/path/*.yaml')
        glob_m.assert_called_with('/some/path/*.yaml')
        open_mock.assert_called_with('/some/path/myfile.yaml', 'r')
        self.assertEqual(result, self._test_data_obj)

    @mock.patch('nailgun.utils.files_manager.glob.glob')
    def test_load_json(self, glob_m):
        open_mock = mock.mock_open(read_data=json.dumps(self._test_data_obj))
        glob_m.return_value = ['/some/path/myfile.json']
        with mock.patch(
                'nailgun.utils.files_manager.open',
                open_mock,
                create=True):
            fm = utils.FilesManager()
            result = fm.load('/some/path/*.json')
        glob_m.assert_called_with('/some/path/*.json')
        open_mock.assert_called_with('/some/path/myfile.json', 'r')
        self.assertEqual(result, self._test_data_obj)

    @mock.patch('nailgun.utils.files_manager.glob.glob')
    def test_load_md(self, glob_m):
        open_mock = mock.mock_open(read_data=self._test_text)
        glob_m.return_value = ['/some/path/myfile.md']
        with mock.patch(
                'nailgun.utils.files_manager.open',
                open_mock,
                create=True):
            fm = utils.FilesManager()
            result = fm.load('/some/path/*.md')
        glob_m.assert_called_with('/some/path/*.md')
        open_mock.assert_called_with('/some/path/myfile.md', 'r')
        self.assertEqual(result, self._test_text)

    @mock.patch('nailgun.utils.files_manager.glob.glob')
    def test_load_several_md(self, glob_m):
        open_mock = mock.mock_open(read_data=self._test_text)
        glob_m.return_value = [
            '/some/path/myfile1.md',
            '/some/path/myfile2.md'
        ]
        with mock.patch(
                'nailgun.utils.files_manager.open',
                open_mock,
                create=True):
            fm = utils.FilesManager()
            result = fm.load('/some/path/*.md')
        glob_m.assert_called_with('/some/path/*.md')

        self.assertEqual(2, open_mock.call_count)
        self.assertEqual(result, [self._test_text] * 2)

    def test_merge_data_records(self):
        fm = utils.FilesManager()
        self.assertItemsEqual(
            {
                'field1': 11,
                'field2': 2
            },
            fm._merge_data_records(
                [
                    {'field1': {'nested_field_to_kill': 1}},
                    {'field2': 2},
                    {'field1': 11},
                ]
            )
        )
        self.assertItemsEqual(
            {
                'field1': 1,
            },
            fm._merge_data_records(
                [
                    {'field1': 1},
                    None,
                ]
            )
        )

        self.assertItemsEqual(
            {
                'field1': 1,
            },
            fm._merge_data_records(
                [
                    {
                        'field1': 1,
                    }
                ]
            )
        )

        self.assertItemsEqual(
            [
                {'field1': 1},
                {'field2': 2},
                {'field1': 11},
            ],
            fm._merge_data_records(
                [
                    [
                        {'field1': 1},
                        {'field2': 2}
                    ],
                    [
                        {'field1': 11},
                    ]
                ]
            )
        )

        self.assertItemsEqual(
            [
                {'field1': 1},
                {'field2': 2},
                {'field1': 11},
            ],
            fm._merge_data_records(
                [
                    [
                        {'field1': 1},
                        {'field2': 2}
                    ],
                    [
                        {'field1': 11},
                    ]
                ]
            )
        )

        self.assertItemsEqual(
            [
                {'field1': 1},
                {'field2': 2}
            ],
            fm._merge_data_records(
                [
                    [
                        {'field1': 1},
                    ],
                    {'field2': 2},

                ]
            )
        )

        self.assertItemsEqual(
            [
                {'field1': 1},
                {'field2': 2}
            ],
            fm._merge_data_records(
                [
                    {'field2': 2},
                    [
                        {'field1': 1},
                    ]

                ]
            )
        )

        self.assertItemsEqual(
            [
                'None',
                None,
                'ZZZ'
            ],
            fm._merge_data_records(
                [
                    'None',
                    None,
                    'ZZZ'
                ]
            )
        )
