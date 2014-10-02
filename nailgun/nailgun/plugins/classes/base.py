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

import abc
import os

import six
import yaml


class NailgunPlugin(six.with_metaclass(abc.ABCMeta, object)):
    __plugin_name__ = None

    config_file = None

    def __init__(self):
        if not self.__plugin_name__:
            raise Exception(
                "__plugin_name__ is not specified!"
            )
        self.plugin_name = self.__plugin_name__
        from nailgun.plugins.storage import PluginStorage
        self.storage = PluginStorage(
            plugin_name=self.plugin_name
        )
        self.config = {}
        if self.config_file:
            self.config.update(self._load_config())

    def _load_config(self):
        if os.access(self.config_file, os.R_OK):
            with open(self.config_file, "r") as conf:
                return yaml.load(conf.read())
