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


@six.add_metaclass(abc.ABCMeta)
class UpgradeEngine(object):
    """Base class for all upgraders.

    The main purpose of this class is to declare interface, which must be
    respected by all upgraders.
    """
    def __init__(self, config):
        """Extract some base parameters and save it internally.
        """
        self.config = config

    @abc.abstractmethod
    def upgrade(self):
        """Run upgrade process.
        """

    @abc.abstractmethod
    def rollback(self):
        """Rollback all the changes, generally used in case of failed upgrade.
        """

    @abc.abstractmethod
    def on_success(self):
        """Here engine can execute some simple actions,
        errors during the execution of this action will
        be ignored and rollback won't be ran
        """

    @abc.abstractproperty
    def required_free_space(self):
        """Required free space for upgarde

        Must return dict where key is path to directory
        and value is required free space in megabytes.

        Example:
          {
            "/var/www/nailgun": 2000,
            "/var/lib/docker": 5000,
            "/etc/supervisor.d": 10,
          }
        """
