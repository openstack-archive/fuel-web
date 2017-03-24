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
from nailgun.expression import Expression
from nailgun.logger import logger
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
            re.compile(r'settings:common\.(.+?)(.value)?'),
            r'settings:\1'
        ),
        (
            # the traverse removes trailing '.value' during serialization
            re.compile(r'settings:(.+?)(.value)(?!\.)'),
            r'settings:\1'
        )
    ]

    def __init__(self, transaction):
        self._transaction = transaction
        self._yaql_context = yaql_ext.create_context(
            add_serializers=True, add_datadiff=True, add_extensions=True
        )
        self._yaql_engine = yaql_ext.create_engine()
        self._yaql_expressions_cache = {}

    def get_transaction_option(self, name, default=None):
        return self._transaction.options.get(name, default)

    def get_new_data(self, node_id):
        return self._transaction.get_new_data(node_id)

    def get_yaql_interpreter(self, node_id, task_id):
        context = self._yaql_context.create_child_context()
        context['$%new'] = self._transaction.get_new_data(node_id)
        context['$%old'] = self._transaction.get_old_data(node_id, task_id)
        context['$node'] = self._transaction.get_new_node_data(node_id)
        context['$common'] = self._transaction.get_new_common_data()
        context['$'] = context['$%new']
        cache = self._yaql_expressions_cache

        def evaluate(expression):
            logger.debug("evaluate yaql expression: %s", expression)
            try:
                parsed_exp = cache[expression]
            except KeyError:
                parsed_exp = self._yaql_engine(expression)
                cache[expression] = parsed_exp
            return parsed_exp.evaluate(context=context)
        return evaluate

    def get_legacy_interpreter(self, node_id):
        deployment_info = self._transaction.get_new_data(node_id)
        context = {
            'cluster': deployment_info.get('cluster', {}),
            'settings': deployment_info
        }

        def evaluate(condition):
            try:
                logger.debug("evaluate legacy condition: %s", condition)
                return Expression(
                    Context.transform_legacy_condition(condition),
                    context,
                    strict=False
                ).evaluate()
            except Exception as e:
                logger.error(
                    "Failed to evaluate legacy condition '%s': %s",
                    condition, e
                )
                raise

        return evaluate

    def get_formatter_context(self, node_id):
        # TODO(akislitsky) remove formatter context from the
        # tasks serialization workflow
        data = self._transaction.get_new_data(node_id)
        return {
            'CLUSTER_ID': data.get('cluster', {}).get('id'),
            'OPENSTACK_VERSION': data.get('openstack_version'),
            'MASTER_IP': settings.MASTER_IP,
            'CN_HOSTNAME': data.get('public_ssl', {}).get('hostname'),
            'SETTINGS': settings
        }

    @classmethod
    def transform_legacy_condition(cls, condition):
        # we need to adjust legacy condition, because current is run
        # on serialized data instead of raw data
        logger.debug("transform legacy expression: %s", condition)
        for pattern, replacement in cls.legacy_condition_transformers:
            condition = re.sub(pattern, replacement, condition)
        logger.debug("the transformation result: %s", condition)
        return condition


@six.add_metaclass(abc.ABCMeta)
class DeploymentTaskSerializer(object):
    fields = frozenset((
        'id', 'type', 'parameters', 'fail_on_error',
        'requires', 'required_for',
        'cross_depends', 'cross_depended_by',
    ))

    @abc.abstractmethod
    def finalize(self, task, node_id):
        """Finish task serialization.

        :param task: the serialized task
        :param node_id: the target node_id
        :return: the result
        """

    def serialize(self, node_id, formatter_context=None):
        """Serialize task in expected by orchestrator format

        If serialization is performed on the remote worker
        we should pass formatter_context parameter with values
        from the master node settings

        :param formatter_context: formatter context
        :param node_id: the target node_id
        """

        logger.debug(
            "serialize task %s for node %s",
            self.task_template['id'], node_id
        )
        formatter_context = formatter_context \
            or self.context.get_formatter_context(node_id)
        task = utils.traverse(
            self.task_template,
            utils.text_format_safe,
            formatter_context,
            {
                'yaql_exp': self.context.get_yaql_interpreter(
                    node_id, self.task_template['id'])
            }
        )
        return self.normalize(self.finalize(task, node_id))

    def normalize(self, task):
        """Removes unnecessary fields.

        :param task: the serialized task
        :return: the task instance
        """
        fields = self.fields
        for k in list(task):
            if k not in fields:
                del task[k]
        return task


class NoopTaskSerializer(DeploymentTaskSerializer):
    def __init__(self, context, task_template):
        self.task_template = task_template
        self.context = context

    def finalize(self, task, node_id):
        task.pop('parameters', None)
        task['type'] = consts.ORCHESTRATOR_TASK_TYPES.skipped
        task['fail_on_error'] = False
        return task


class DefaultTaskSerializer(NoopTaskSerializer):

    def should_execute(self, task, node_id):
        condition = task.get('condition', True)
        if isinstance(condition, six.string_types):
            # string condition interprets as legacy condition
            # and it should be evaluated
            interpreter = self.context.get_legacy_interpreter(node_id)
            return interpreter(condition)
        return condition

    def finalize(self, task, node_id):
        if not self.should_execute(task, node_id):
            logger.debug(
                "Task %s is skipped by condition.", task['id']
            )
            return super(DefaultTaskSerializer, self).finalize(task, node_id)

        task.setdefault('parameters', {}).setdefault('cwd', '/')
        task.setdefault('fail_on_error', True)
        return task


class TasksSerializersFactory(object):
    known_types = {
        consts.ORCHESTRATOR_TASK_TYPES.skipped: NoopTaskSerializer,
        consts.ORCHESTRATOR_TASK_TYPES.stage: NoopTaskSerializer,
    }

    def __init__(self, transaction):
        self.context = Context(transaction)

    def create_serializer(self, task_template):
        serializer_class = self.known_types.get(
            task_template['type'], DefaultTaskSerializer
        )
        return serializer_class(self.context, task_template)
