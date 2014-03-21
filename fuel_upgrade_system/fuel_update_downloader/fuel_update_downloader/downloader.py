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

from fuel_update_downloader import errors

from fuel_update_downloader.utils import calculate_free_space
from fuel_update_downloader.utils import calculate_md5sum
from fuel_update_downloader.utils import download_file


class Downloader(object):
    """Class implements downloading logic
    """

    def __init__(self, src_path, dst_path, required_free_space, checksum):
        """Create downloader object

        :param src_path: source path
        :param dst_path: destination path
        :param required_free_space: require free space
        :param checksum: checksum of file
        """
        self.src_path = src_path
        self.dst_path = dst_path
        self.required_free_space = required_free_space
        self.checksum = checksum

    def run(self):
        """Run downloading and checkings
        """
        self._check_free_space()
        download_file(self.src_path, self.dst_path)
        self._check_checksum()

    def _check_free_space(self):
        """Check `self.dst_path` free space

        :raises: errors.NotEnoughFreeSpace
        """
        free_space = calculate_free_space(self.dst_path)
        if free_space < self.required_free_space:
            raise errors.NotEnoughFreeSpace(
                'Not enough free space, path - "{0}", '
                'free space - "{1}", '
                'required free space - "{2}"'.format(
                    self.dst_path, free_space, self.required_free_space))

    def _check_checksum(self):
        """Calculate checksum and compare it with `self.checksum`

        :raises: errors.WrongChecksum
        """
        calculated_checksum = calculate_md5sum(self.dst_path)
        if calculated_checksum != self.checksum:
            raise errors.WrongChecksum(
                'File "{0}" has wrong checkum, actual '
                'checksum "{1}" expected checksum "{2}"'.format(
                    self.dst_path, calculated_checksum, self.checksum))
