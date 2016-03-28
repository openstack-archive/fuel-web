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

from nailgun import consts
from nailgun.errors import errors
from nailgun.expression import Expression
from nailgun.settings import settings
from nailgun import utils
from nailgun import yaql_ext


class Context(object):
    # Because condition runs on serialized data instead of raw data
    # we have to modify name of variables, the following transformations
    # will adjust legacy conditions for using with serialized data
    # all conditions in core tasks was replaced by YAQL expression,
    # this code needs only for supporting compatibility with plugins

    legacy_condition_transformers = [
        (
            # additional_components section is merged to root on serialization
            re.compile(r'settings:additional_components\.(\w+)(\.value)?'),
            r'settings:\1.enabled'
        ),
        (
            # common section is merged to root on serialization
            re.compile(r'settings:common\.(.+)(.value)?'),
            r'settings:\1'
        ),
        (
            # the traverse removes trailing '.value' during serialization
            re.compile(r'settings:(.+)(.value)(?!\.)'),
            r'settings:\1'
        )
    ]

    def __init__(self, transaction):
        self._transaction = transaction
        self._yaql_context = yaql_ext.create_context(
            add_serializers=True, add_datadiff=True
        )
        self._yaql_expressions_cache = {}

    def get_new_data(self, node_id):
        return self._transaction.get_new_data(node_id)

    def get_yaql_interpreter(self, node_id):
        context = self._yaql_context.create_child_context()
        context['$%new'] = self._transaction.get_new_data(node_id)
        context['$%old'] = self._transaction.get_old_data(node_id)
        cache = self._yaql_expressions_cache

        def evaluate(expression):
            try:
                parsed_exp = cache[expression]
            except KeyError:
                parsed_exp = yaql_ext.create_engine()(expression)
                cache[expression] = parsed_exp
            return parsed_exp.evaluate(data=context['$%new'], context=context)
        return evaluate

    def get_legacy_interpreter(self, node_id):
        deployment_info = self._transaction.get_new_data(node_id)
        context = {
            'cluster': deployment_info['cluster'],
            'settings': deployment_info
        }

        def evaluate(condition):
            return Expression(
                Context.transform_legacy_condition(condition), context
            ).evaluate()

        return evaluate

    def get_formatter_context(self, node_id):
        deployment_info = self._transaction.get_new_data(node_id)
        return {
            'CLUSTER_ID': deployment_info['cluster']['id'],
            'OPENSTACK_VERSION': deployment_info['openstack_version'],
            'MASTER_IP': settings.MASTER_IP,
            'CN_HOSTNAME': deployment_info['public_ssl']['hostname'],
            'SETTINGS': settings
        }

    @classmethod
    def transform_legacy_condition(cls, condition):
        # we need to adjust legacy condition, because current is run
        # on serialized data instead of raw data
        for pattern, replacement in cls.legacy_condition_transformers:
            condition = re.sub(pattern, replacement, condition)
        return condition


@six.add_metaclass(abc.ABCMeta)
class DeploymentTaskSerializer(object):
    fields = frozenset((
        'id', 'type', 'parameters', 'fail_on_error',
        'requires', 'required_for',
        'cross_depends', 'cross_depended_by',
    ))

    @abc.abstractmethod
    def serialize(self, node_id):
        """Serialize task in expected by orchestrator format.

        This interface should return generator, because in some cases one
        external task - should serialize several tasks internally.

        :param node_id: the target node_id
        """

    @classmethod
    def finalize(cls, task, fields=None):
        """Gets rid off extra attributes.

        :param task: the serialized task
        :param fields: the list of fields for including
        """
        return {k: task.get(k) for k in (fields or cls.fields)}


class NoopTaskSerializer(DeploymentTaskSerializer):
    def __init__(self, context, task_template):
        self.task_template = task_template
        self.context = context

    def serialize(self, node_id):
        task = self.finalize(
            self.task_template, self.fields - {'parameters'}
        )
        task['type'] = consts.ORCHESTRATOR_TASK_TYPES.skipped
        task['fail_on_error'] = False
        return task


class DefaultTaskSerializer(NoopTaskSerializer):
    def should_execute(self, task, node_id):
        if 'condition' not in task:
            return True

        if isinstance(task['condition'], six.string_types):
            # the utils.traverse removes all '.value' attributes.
            # the option prune_value_attribute is used
            # to keep backward compatibility
            interpreter = self.context.get_legacy_interpreter(node_id)
            return interpreter(self.task_template['condition'])
        return task['condition']

    def serialize(self, node_id):
        task = utils.traverse(
            self.task_template,
            utils.text_format_safe,
            self.context.get_formatter_context(node_id),
            {
                'yaql_exp': self.context.get_yaql_interpreter(node_id)
            }
        )
        if not self.should_execute(task, node_id):
            return super(DefaultTaskSerializer, self).serialize(node_id)

        task.setdefault('parameters', {}).setdefault('cwd', '/')
        task.setdefault('fail_on_error', True)
        return self.finalize(task)


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
