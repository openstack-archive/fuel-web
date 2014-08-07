# Copyright 2014 Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from fuel_agent import errors


class Image(object):
    SUPPORTED_CONTAINERS = ['raw', 'gzip']

    def __init__(self, uri, target_device,
                 image_format, container, size=None):
        # uri is something like
        # http://host:port/path/to/image.img or
        # file:///tmp/image.img
        self.uri = uri
        self.target_device = target_device
        # this must be one of 'iso9660', 'ext[234]', 'xfs'
        self.image_format = image_format
        if container not in self.SUPPORTED_CONTAINERS:
            raise errors.WrongImageDataError(
                'Error while image initialization: '
                'unsupported image container')
        self.container = container
        self.size = size


class ImageScheme(object):
    def __init__(self, images=None):
        self.images = images or []

    def add_image(self, **kwargs):
        self.images.append(Image(**kwargs))
