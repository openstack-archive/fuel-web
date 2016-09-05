# -*- coding: utf-8 -*-

#    Copyright 2016 Mirantis, Inc.
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

from itertools import chain

from stevedore.extension import ExtensionManager

from nailgun.db import db
from nailgun.errors import errors
from nailgun.extensions import consts

_EXTENSION_MANAGER = None


def get_all_extensions():
    """Retrieves all available extensions for Nailgun

    :returns: generator of extensions objects
    """
    # NOTE(sbrzeczkowski): in order to not cause circular imports from
    # extensions and not creating instances ExtensionManager on every time
    # this function is called, we use 'global' variable.
    global _EXTENSION_MANAGER

    if _EXTENSION_MANAGER is None:
        _EXTENSION_MANAGER = ExtensionManager(
            namespace=consts.EXTENSIONS_NAMESPACE
        )

    return (ext.plugin for ext in _EXTENSION_MANAGER.extensions)


def get_extension(name):
    """Retrieves extension by name

    :param str name: name of the extension
    :returns: extension class
    :raises errors.CannotFindExtension: on non existing extension
    """
    extension = next(
        (ext for ext in get_all_extensions() if ext.name == name), None)

    if extension is not None:
        return extension

    raise errors.CannotFindExtension(
        "Cannot find extension with name '{0}'".format(name))


def set_extensions_for_object(obj, extensions_names):
    obj.extensions = extensions_names
    db().flush()


def _get_extension_by_node(call_name, node):
    all_extensions = {ext.name: ext for ext in get_all_extensions()}
    for extension in chain(node.extensions,
                           node.cluster.extensions if node.cluster else []):

        if (extension in all_extensions and
                call_name in all_extensions[extension].provides):
            return all_extensions[extension]

    raise errors.CannotFindExtension("Cannot find extension which provides "
                                     "'{0}' call".format(call_name))


def node_extension_call(call_name, node, *args, **kwargs):
    # NOTE(sbrzeczkowski): should be removed once data-pipeline blueprint is
    # done: https://blueprints.launchpad.net/fuel/+spec/data-pipeline
    extension = _get_extension_by_node(call_name, node)
    return getattr(extension, call_name)(node, *args, **kwargs)


def setup_yaql_context(yaql_context):
    for extension in get_all_extensions():
        extension.setup_yaql_context(yaql_context)


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


def _collect_data_pipelines_for_cluster(cluster):
    return chain.from_iterable(
        e.data_pipelines for e in _collect_extensions_for_cluster(cluster))


def _collect_extensions_for_cluster(cluster):
    for e in cluster.extensions:
        yield get_extension(e)


def fire_callback_on_node_serialization_for_deployment(node, node_data):
    for pipeline in _collect_data_pipelines_for_cluster(node.cluster):
        pipeline.process_deployment_for_node(node, node_data)


def fire_callback_on_node_serialization_for_provisioning(node, node_data):
    for pipeline in _collect_data_pipelines_for_cluster(node.cluster):
        pipeline.process_provisioning_for_node(node, node_data)


def fire_callback_on_cluster_serialization_for_deployment(cluster, data):
    for pipeline in _collect_data_pipelines_for_cluster(cluster):
        pipeline.process_deployment_for_cluster(cluster, data)


def fire_callback_on_cluster_serialization_for_provisioning(cluster, data):
    for pipeline in _collect_data_pipelines_for_cluster(cluster):
        pipeline.process_provisioning_for_cluster(cluster, data)
