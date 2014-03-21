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

from mock import patch

from fuel_update_downloader import errors

from fuel_update_downloader.downloader import Downloader
from fuel_update_downloader.tests.base import BaseTestCase


@patch('fuel_update_downloader.downloader.download_file')
class TestDownloaderUnit(BaseTestCase):

    def default_args(self, **kwargs):
        default = {
            'src_path': 'file:///tmp/src_file',
            'dst_path': '/tmp/dst_file',
            'required_free_space': 100,
            'checksum': ''}

        default.update(kwargs)
        return default

    @patch(
        'fuel_update_downloader.downloader.calculate_free_space',
        return_value=101)
    @patch(
        'fuel_update_downloader.downloader.calculate_md5sum',
        return_value='')
    def test_run_without_errors(self, _, __, ___):
        downloader = Downloader(**self.default_args())
        downloader.run()

    def test_run_error_in_case_if_disk_does_not_have_enough_space(self, _):
        kwargs = self.default_args(required_free_space=1000)
        downloader = Downloader(**kwargs)

        with patch(
                'fuel_update_downloader.downloader.calculate_free_space',
                return_value=1):

            self.assertRaisesRegexp(
                errors.NotEnoughFreeSpace,
                'Not enough free space, path - "/tmp/dst_file", '
                'free space - "1", required free space - "1000"',
                downloader.run)

    def test_run_error_in_case_if_md5_sums_are_not_equal(
            self, download_file_mock):

        kwargs = self.default_args(required_free_space=1000)
        downloader = Downloader(**kwargs)

        with patch(
                'fuel_update_downloader.downloader.calculate_md5sum',
                return_value='wrong_md5_sum'):

            self.assertRaisesRegexp(
                errors.WrongChecksum,
                'File "/tmp/dst_file" has wrong checkum, actual '
                'checksum "wrong_md5_sum" expected checksum ""',
                downloader.run)
