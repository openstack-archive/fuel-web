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

import abc
import re

import six
import yaml

from nailgun import consts
from nailgun.errors import errors
from nailgun.expression import Expression
from nailgun.settings import settings
from nailgun import utils


class TaskAttributesGenerator(utils.AttributesGenerator):
    def __init__(self, deployment_info):
        self.deployment_info = deployment_info

    def __call__(self, name, arg=None):
        return getattr(self, name)(arg)

    def from_deployment_info(self, arg):
        try:
            v = self.deployment_info
            if arg:
                for a in arg.split('.'):
                    v = v[a]
            return v
        except Exception as e:
            raise ValueError("Invalid argument: '{0}': {1}".format(arg, e))

    def from_deployment_info_as_yaml(self, arg):
        return yaml.safe_dump(self.from_deployment_info(arg))


class Context(object):
    legacy_condition_transformers = [
        (
            # additional_components section is removed from attributes
            # nailgun/objects/cluster.py:115
            re.compile(r'settings:additional_components\.(\w+)(\.value)?'),
            r'settings:\1.enabled'
        ),
        (
            # common section is removed from cluster attributes
            # nailgun/objects/cluster.py:113
            re.compile(r'settings:common\.(.+)(.value)?'),
            r'settings:\1'
        ),
        (
            # traverse removes trailing '.value'
            re.compile(r'settings:(.+)(.value)(?!\.)'),
            r'settings:\1'
        )
    ]

    def __init__(self, transaction):
        self.transaction = transaction

    def get_new_data(self, node_id):
        return self.transaction.get_new_data(node_id)

    def get_attribute_generator(self, node_id):
        return TaskAttributesGenerator(self.transaction.get_new_data(node_id))

    def get_legacy_interpreter(self, node_id):
        deployment_info = self.transaction.get_new_data(node_id)
        context = {
            'cluster': deployment_info['environment'],
            'settings': deployment_info
        }

        def evaluate(condition):
            return Expression(
                Context.transform_legacy_condition(condition), context
            ).evaluate()

        return evaluate

    def get_formatter_context(self, node_id):
        deployment_info = self.transaction.get_new_data(node_id)
        return {
            'CLUSTER_ID': deployment_info['environment']['id'],
            'OPENSTACK_VERSION': deployment_info['openstack_version'],
            'MASTER_IP': settings.MASTER_IP,
            'CN_HOSTNAME': deployment_info['public_ssl']['hostname'],
            'SETTINGS': settings
        }

    @classmethod
    def transform_legacy_condition(cls, condition):
        # there is 3 things that is changed and need to convert condition

        # additional_components merges with root
        # nailgun.objects.cluster.Attributes#merged_attrs_values

        for pattern, replacement in cls.legacy_condition_transformers:
            condition = re.sub(pattern, replacement, condition)
        return condition


@six.add_metaclass(abc.ABCMeta)
class DeploymentTaskSerializer(object):
    @abc.abstractmethod
    def serialize(self, node_id):
        """Serialize task in expected by orchestrator format.

        This interface should return generator, because in some cases one
        external task - should serialize several tasks internally.

        :param node_id: the target node_id
        """


class NoopTaskSerializer(DeploymentTaskSerializer):
    def __init__(self, context, task_template):
        self.task_template = task_template
        self.context = context

    def serialize(self, node_id):
        return {
            'id': self.task_template['id'],
            'type': consts.ORCHESTRATOR_TASK_TYPES.skipped,
            'fail_on_error': False,
            'requires': self.task_template.get('requires'),
            'required_for': self.task_template.get('required_for'),
            'cross_depends': self.task_template.get('cross_depends'),
            'cross_depended_by': self.task_template.get('cross_depended_by'),
        }


class DefaultTaskSerializer(NoopTaskSerializer):
    hidden_attributes = ('roles', 'role', 'groups', 'condition')

    def should_execute(self, node_id):
        if 'condition' not in self.task_template:
            return True

        # the utils.traverse removes all '.value' attributes.
        # the option prune_value_attribute is used
        # to keep backward compatibility
        interpreter = self.context.get_legacy_interpreter(node_id)
        return interpreter(self.task_template['condition'])

    def serialize(self, node_id):
        if not self.should_execute(node_id):
            return super(DefaultTaskSerializer, self).serialize(node_id)

        task = utils.traverse(
            self.task_template,
            self.context.get_attribute_generator(node_id),
            self.context.get_formatter_context(node_id),
            formatter=utils.text_format_safe
        )
        task.setdefault('parameters', {}).setdefault('cwd', '/')
        task.setdefault('fail_on_error', True)
        for attr in self.hidden_attributes:
            task.pop(attr, None)
        return task


def handle_unsupported(_, task_template):
    raise errors.SerializerNotSupported(
        'The task with type {0} is not supported.'
        .format(task_template['type'])
    )


class TasksSerializersFactory(object):
    known_types = {
        consts.ORCHESTRATOR_TASK_TYPES.skipped: NoopTaskSerializer,
        consts.ORCHESTRATOR_TASK_TYPES.stage: NoopTaskSerializer,
        consts.ORCHESTRATOR_TASK_TYPES.copy_files: DefaultTaskSerializer,
        consts.ORCHESTRATOR_TASK_TYPES.puppet: DefaultTaskSerializer,
        consts.ORCHESTRATOR_TASK_TYPES.reboot: DefaultTaskSerializer,
        consts.ORCHESTRATOR_TASK_TYPES.shell: DefaultTaskSerializer,
        consts.ORCHESTRATOR_TASK_TYPES.sync: DefaultTaskSerializer,
        consts.ORCHESTRATOR_TASK_TYPES.upload_file: DefaultTaskSerializer,
    }

    def __init__(self, transaction):
        self.context = Context(transaction)

    def create_serializer(self, task_template):
        serializer_class = self.known_types.get(
            task_template['type'], handle_unsupported
        )
        return serializer_class(self.context, task_template)
