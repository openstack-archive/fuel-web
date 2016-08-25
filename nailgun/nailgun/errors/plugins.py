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


class PluginException(NailgunException):
    """Base plugin exception."""


class PackageFormatIsNotCompatible(PluginException):
    message = "Package format is not compatible"


class PackageVersionIsNotCompatible(PluginException):
    message = "Package version is not compatible"


class NoPluginFileFound(PluginException):
    message = "Plugin file not found"


class UpgradeIsNotSupported(PluginException):
    message = "Upgrade is not supported"


class DowngradeIsNotSupported(PluginException):
    message = "Downgrade is not supported"


class ShellError(PluginException):
    message = "Shell command executed with an error"
