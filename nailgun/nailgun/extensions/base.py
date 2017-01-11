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

# Contains base class for Nailgun extensions

import abc

import six


class DeprecationController(type):
    @staticmethod
    def mark_as_deprecated(obj, details):
        obj.__deprecated__ = details

    @staticmethod
    def is_deprecated(obj):
        return hasattr(obj, '__deprecated__')

    def __new__(mcls, name, bases, namespace):
        cls = super(DeprecationController, mcls).__new__(
            mcls, name, bases, namespace
        )
        deprecated_methods = set()
        for base in bases:
            for name in dir(base):
                value = getattr(base, name, None)
                # if method from base class has attribute '__deprectated__'
                # and method from current class does not have, that means
                # method was overridden in current class and it needs
                # to inform user that method was removed
                if (
                    DeprecationController.is_deprecated(value) and
                    not DeprecationController.is_deprecated(getattr(cls, name))
                ):
                    deprecated_methods.add((base, value))

        if deprecated_methods:
            raise RuntimeError(
                '\n'.join(
                    "{0}.{1} was removed. {2}.".format(
                        c.__name__, m.__name__, m.__deprecated__
                    ) for c, m in deprecated_methods
                )
            )

        return cls


def deprecated(instructions):
    def wrapper(func):
        DeprecationController.mark_as_deprecated(func, instructions)
        return func
    return wrapper


@six.add_metaclass(DeprecationController)
class BasePipeline(object):
    @classmethod
    def process_deployment_for_cluster(cls, cluster, cluster_data):
        """Extend or modify deployment data for cluster.

        :param cluster_data: serialized data for cluster
        :param cluster: the instance of Cluster
        """

    @classmethod
    def process_deployment_for_node(cls, node, node_data):
        """Extend or modify deployment data for node.

        :param node: the instance of Node
        :param node_data: serialized data for node
        """

    @classmethod
    def process_provisioning_for_cluster(cls, cluster, cluster_data):
        """Extend or modify provisioning data for cluster.

        :param cluster: the instance of Cluster
        :param cluster_data: serialized data for cluster
        """

    @classmethod
    def process_provisioning_for_node(cls, node, node_data):
        """Extend or modify provisioning data for node.

        :param node: the instance of Node
        :param node_data: serialized data for node
        """

    @classmethod
    @deprecated("Please implement methods process_deployment_for_* instead")
    def process_deployment(cls, deployment_data, cluster, nodes, **kwargs):
        """Change the deployment_data.

        :param deployment_data: serialized data
        """

    @classmethod
    @deprecated("Please implement methods process_provisioning_for_* instead")
    def process_provisioning(cls, provisioning_data, cluster, nodes, **kwargs):
        """Change the provisioning_data.

        :param provisioning_data: serialized data
        """


@six.add_metaclass(abc.ABCMeta)
class BaseExtension(object):
    """Base class for Nailgun extension

    If extension provides API, define here urls in then following format:
    urls = [
      {
        "uri": r'/new/url',
        "handler": HandlerClass
      }
    ]

    If extension needs to manipulate provisioning or deployment data it should
    define data_pipelines list which is a list of BasePipeline sub-classes:

    data_pipelines = [
        ExamplePipelineClass,
        ExamplePipelineClass2,
    ]

    Specify a list of calls which extension provides (not required):

    provides = [
        'method_1',
        'method_2',
    ]

    """
    urls = []
    data_pipelines = []
    provides = []

    @classmethod
    def alembic_migrations_path(cls):
        """Path to alembic migrations (if extension provides any)"""
        return None

    @abc.abstractproperty
    def name(self):
        """Uniq name of the extension."""

    @abc.abstractproperty
    def description(self):
        """Brief description of extension"""

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
    def setup_yaql_context(cls, yaql_context):
        """Setup YAQL context that is going to be used for serialization"""

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
    def on_remove_node_from_cluster(cls, node):
        """Callback which gets executed when node is removed from a cluster"""

    @classmethod
    def on_node_collection_delete(cls, node_ids):
        """Callback which gets executed when node collection is deleted"""

    @classmethod
    def on_nodegroup_create(cls, nodegroup):
        """Callback which gets executed when node group is created"""

    @classmethod
    def on_nodegroup_delete(cls, nodegroup):
        """Callback which gets executed when node group is deleted"""

    @classmethod
    def on_cluster_create(cls, cluster, data):
        """Callback which gets executed when cluster is initially created.

        This is called after the cluster object is created, attributes have
        been created and the default extensions list has been set.
        """

    @classmethod
    def on_cluster_patch_attributes(cls, cluster, public_map):
        """Callback which gets executed when cluster attributes are updated"""

    @classmethod
    def on_cluster_delete(cls, cluster):
        """Callback which gets executed when cluster is deleted"""

    @classmethod
    def on_before_deployment_check(cls, cluster, nodes):
        """Callback which gets executed when "before deployment check" runs"""

    @classmethod
    def on_before_deployment_serialization(cls, cluster, nodes,
                                           ignore_customized):
        """Callback which gets executed before deployment serialization"""

    @classmethod
    def on_before_provisioning_serialization(cls, cluster, nodes,
                                             ignore_customized):
        """Callback which gets executed before provisioning serialization"""

    def to_dict(self):
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "provides": self.provides,
        }
