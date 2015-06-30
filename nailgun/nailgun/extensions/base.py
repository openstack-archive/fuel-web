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


def find_extension(name, version=None):
    pass


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

    @classmethod
    def alembic_migrations_path(cls):
        """If extension provides database migrations,
        the method should return path to alembic migrations
        """
        return None

    @abc.abstractproperty
    def name(self):
        """Uniq name of the extension."""

    @abc.abstractproperty
    def version(self):
        """Version of the extension, follow semantic
        versioning schema (http://semver.org/)
        """

    @classmethod
    def full_name(cls):
        """Returns extension's name and version in human readable format
        """
        return '{0}-{1}'.format(cls.name, cls.version)

    @classmethod
    def table_prefix(cls):
        return '{0}_{1}_'.format(cls.name, cls.version.replace('.', '_'))

    @classmethod
    def alembic_table_version(cls):
        return '{0}alembic_version'.format(cls.table_prefix())
