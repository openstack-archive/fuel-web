# coding: utf-8

# Copyright 2016 Mirantis, Inc.
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

from .base import NailgunException


class InvalidFileFormat(NailgunException):
    message = "Invalid file format: {}, supported formats are: {}"

    def __init__(self, path, supported_formats, *args, **kwargs):
        super(InvalidFileFormat, self).__init__(*args, **kwargs)
        self.message = self.message.format(path, ', '.join(supported_formats))
