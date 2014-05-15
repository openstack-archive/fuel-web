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

import os

import mock
from mock import patch

from StringIO import StringIO

from fuel_update_downloader.tests.base import BaseTestCase
from fuel_update_downloader.utils import byte_to_megabyte
from fuel_update_downloader.utils import calculate_free_space
from fuel_update_downloader.utils import calculate_md5sum
from fuel_update_downloader.utils import download_file


class FakeFile(StringIO):
    """It's a fake file which returns StringIO
    when file opens with 'with' statement.

    NOTE(eli): We cannot use mock_open from mock library
    here, because it hangs when we use 'with' statement,
    and when we want to read file by chunks.
    """
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class TestUtils(BaseTestCase):

    def test_byte_to_megabyte(self):
        self.assertEqual(byte_to_megabyte(0), 0)
        self.assertEqual(byte_to_megabyte(1048576), 1)

    def test_calculate_free_space(self):
        dev_info = mock.Mock()
        dev_info.f_bsize = 1048576
        dev_info.f_bavail = 2
        with patch.object(os, 'statvfs', return_value=dev_info) as st_mock:
            self.assertEqual(calculate_free_space('/tmp/dir/file'), 2)

        st_mock.assert_called_once_with('/tmp/dir')

    def test_calculate_md5sum(self):
        open_mock = mock.MagicMock(return_value=FakeFile('fake file content'))
        file_path = '/tmp/file'

        with mock.patch('__builtin__.open', open_mock):
            self.assertEqual(
                calculate_md5sum(file_path),
                '199df6f47108545693b5c9cb5344bf13')

        open_mock.assert_called_once_with(file_path, 'rb')

    def test_download_file(self):
        content = 'Some content'
        fake_src = StringIO(content)
        fake_file = FakeFile('')
        file_mock = mock.MagicMock(return_value=fake_file)

        src_path = 'http://0.0.0.0:80/tmp/file'
        dst_path = '/tmp/file'

        with mock.patch('urllib2.urlopen', return_value=fake_src) as url_fake:
            with mock.patch('__builtin__.open', file_mock):
                download_file(src_path, dst_path)

        file_mock.assert_called_once_with(dst_path, 'wb')
        url_fake.assert_called_once_with(src_path)
        self.assertEqual(fake_file.getvalue(), content)
