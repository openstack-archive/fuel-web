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

import hashlib
import os
import urllib2


def download_file(src, dst, chunk_size=2 ** 20):
    """Download file

    :param src: download from
    :param dst: download to
    :param chunk_size: optional parameter, size of chunk
    """
    with open(dst, 'wb') as f:
        for chunk in urllib2.urlopen(src).read(chunk_size):
            f.write(chunk)


def calculate_md5sum(file_path, chunk_size=2 ** 20):
    """Calculate file's checksum

    :param file_path: file path
    :param chunk_size: optional parameter, size of chunk
    :returns: md5sum string
    """
    # TODO(el): maybe it will be much faster to use
    # linux md5sum command line utility
    md5 = hashlib.md5()

    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(chunk_size), b''):
            md5.update(chunk)

    return md5.hexdigest()


def calculate_free_space(path):
    """Calculate free space

    :returns: free space in megabytes
    """
    directory = os.path.dirname(path)
    device_info = os.statvfs(directory)
    return byte_to_megabyte(device_info.f_bsize * device_info.f_bavail)


def byte_to_megabyte(byte):
    """Convert bytes to megabytes
    """
    return byte / 1024 ** 2
