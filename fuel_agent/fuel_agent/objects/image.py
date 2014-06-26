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

from fuel_agent.utils import img_utils as iu


class Image(object):
    def __init__(self, uri, image_format, target_device, container,
                 size=None):
        self.uri = uri
        self.image_format = image_format
        self.target_device = target_device
        self.container = container
        self.size = size


class ImageScheme(object):
    def __init__(self, images=None):
        self.images = images or []

    def add_image(self, **kwargs):
        self.images.append(Image(**kwargs))

