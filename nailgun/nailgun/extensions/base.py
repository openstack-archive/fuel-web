# -*- coding: utf-8 -*-

#    Copyright 2015 Mirantis, Inc.
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


import abc
import six


def get_all_extensions():
    # TODO(eli): implement extensions autodiscovery
    # should be done as a part of blueprint
    # https://blueprints.launchpad.net/fuel/+spec/volume-manager-refactoring
    from nailgun.extensions.volume_manager.extension \
        import VolumeManagerExtension

    return [VolumeManagerExtension]


@six.add_metaclass(abc.ABCMeta)
class BaseExtension(object):

    # If extension provides API, define here urls in then
    # next format:
    # [
    #   {
    #     "uri": r'/new/url',
    #     "handler": HandlerClass
    #   }
    # ]
    urls = []

    @abc.abstractproperty
    def name(self):
        """Uniq name of the extension"""

    @abc.abstractproperty
    def version(self):
        """Version of the extension, follow semantic
        versioning schema (http://semver.org/)
        """
