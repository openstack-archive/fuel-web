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

from nailgun.errors import errors


def get_all_extensions():
    # TODO(eli): implement extensions autodiscovery
    # should be done as a part of blueprint
    # https://blueprints.launchpad.net/fuel/+spec/volume-manager-refactoring
    from nailgun.extensions.cluster_upgrade.extension \
        import ClusterUpgradeExtension
    from nailgun.extensions.volume_manager.extension \
        import VolumeManagerExtension
    from nailgun.extensions.bareon.extension import BareonExtension

    extensions = [
        VolumeManagerExtension,
        ClusterUpgradeExtension,
        BareonExtension,
    ]
    return extensions


def get_extension(name):
    """Retrieves extension by name

    :param str name: name of the extension
    :returns: extension class
    """
    extensions = filter(lambda e: e.name == name, get_all_extensions())

    if not extensions:
        raise errors.CannotFindExtension(
            "Cannot find extension with name '{0}'".format(name))

    return extensions[0]


def _get_extension_by_node_or_env(call_name, node):
    found_extension = None

    # Try to find extension in node
    if node:
        for extension in node.extensions:
            if call_name in get_extension(extension).provides:
                found_extension = extension

    # Try to find extension by environment
    if not found_extension and node.cluster:
        for extension in node.cluster.extensions:
            if call_name in get_extension(extension).provides:
                found_extension = extension

    if not found_extension:
        raise errors.CannotFindExtension(
            "Cannot find extension which provides "
            "'{0}' call".format(call_name))

    return get_extension(found_extension)


def node_extension_call(call_name, node, *args, **kwargs):
    extension = _get_extension_by_node_or_env(call_name, node)

    return getattr(extension, call_name)(node, *args, **kwargs)


def fire_callback_on_node_create(node):
    for extension in get_all_extensions():
        extension.on_node_create(node)


def fire_callback_on_node_update(node):
    for extension in get_all_extensions():
        extension.on_node_update(node)


def fire_callback_on_node_reset(node):
    for extension in get_all_extensions():
        extension.on_node_reset(node)


def fire_callback_on_node_delete(node):
    for extension in get_all_extensions():
        extension.on_node_delete(node)


def fire_callback_on_node_collection_delete(node_ids):
    for extension in get_all_extensions():
        extension.on_node_collection_delete(node_ids)


def fire_callback_on_cluster_delete(cluster):
    for extension in get_all_extensions():
        extension.on_cluster_delete(cluster)


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

    # Specify a list of calls which extension provides.
    # This list is required for core and other extensions
    # to find extension with specific functionality.
    provides = []

    @classmethod
    def alembic_migrations_path(cls):
        """Path to alembic migrations (if extension provides any)"""
        return None

    @abc.abstractproperty
    def name(self):
        """Uniq name of the extension."""

    @abc.abstractproperty
    def version(self):
        """Version of the extension

        Follows semantic versioning schema (http://semver.org/)
        """

    @classmethod
    def full_name(cls):
        """Returns extension's name and version in human readable format"""
        return '{0}-{1}'.format(cls.name, cls.version)

    @classmethod
    def table_prefix(cls):
        return '{0}_'.format(cls.name)

    @classmethod
    def alembic_table_version(cls):
        return '{0}alembic_version'.format(cls.table_prefix())

    @classmethod
    def on_node_create(cls, node):
        """Callback which gets executed when node is created"""

    @classmethod
    def on_node_update(cls, node):
        """Callback which gets executed when node is updated"""

    @classmethod
    def on_node_reset(cls, node):
        """Callback which gets executed when node is reseted"""

    @classmethod
    def on_node_delete(cls, node):
        """Callback which gets executed when node is deleted"""

    @classmethod
    def on_node_collection_delete(cls, node_ids):
        """Callback which gets executed when node collection is deleted"""

    @classmethod
    def on_cluster_delete(cls, cluster):
        """Callback which gets executed when cluster is deleted"""
