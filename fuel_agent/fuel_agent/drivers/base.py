# Copyright 2015 Mirantis, Inc.
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

import abc
import copy

import six


@six.add_metaclass(abc.ABCMeta)
class BaseDataDriver(object):
    """Data driver API

    For example, data validation methods,
    methods for getting object schemes, etc.
    """

    def __init__(self, data):
        self.data = copy.deepcopy(data)

    @abc.abstractproperty
    def partition_scheme(self):
        """Retruns instance of PartionScheme object"""

    @abc.abstractproperty
    def image_scheme(self):
        """Returns instance of ImageScheme object"""

    @abc.abstractproperty
    def grub(self):
        """Returns instance of Grub object"""

    @abc.abstractproperty
    def operating_system(self):
        """Returns instance of OperatingSystem object"""

    @abc.abstractproperty
    def configdrive_scheme(self):
        """Returns instance of ConfigDriveScheme object"""
