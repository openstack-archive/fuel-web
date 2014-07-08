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

import abc
import six

import logging

logger = logging.getLogger(__name__)


@six.add_metaclass(abc.ABCMeta)
class PreUpgradeHookBase(object):
    """Abstract class for pre upgrade hooks

    :param list upgraders: list of :class:`BaseUpgrader` implementations
    :param config: :class:`Config` object
    """

    def __init__(self, upgraders, config):
        self.config = config
        self.upgraders = upgraders

    @abc.abstractproperty
    def is_required(self):
        """
        """

    @property
    def is_enabled_for_engines(self):
        """Checks if engine in the list

        :returns: True if engine in the list
                  False if engine not in the list
        """
        for engine in self._enable_for_engines:
            for upgrade in self.upgraders:
                if isinstance(engine, upgrade):
                    return True

        return False

    @abc.abstractproperty
    def _enable_for_engines(self):
        """
        """
        

    @abc.abstractmethod
    def run(self):
        """
        """
