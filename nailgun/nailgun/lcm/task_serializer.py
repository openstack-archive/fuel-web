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
import six

from nailgun import consts
from nailgun.expression import Expression
from nailgun.settings import settings
from nailgun import utils


class TaskAttributesGenerator(utils.AttributesGenerator):
    def __init__(self, deployment_info):
        self.deployment_info = deployment_info

    def from_deployment_info(self, arg):
        try:
            v = self.deployment_info
            if arg:
                for a in arg.split('.'):
                    v = v[a]
            return v
        except Exception as e:
            raise ValueError("Invalid argument: '{0}': {1}".format(arg, e))


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
    hidden_attributes = ('roles', 'groups', 'condition')

    def should_execute(self, node_id):
        if 'condition' not in self.task_template:
            return True
        return Expression(
            self.task_template['condition'],
            self.get_legacy_expression_context(node_id)
        ).evaluate()

    def serialize(self, node_id):
        deployment_info = self.context.get_deployment_info(node_id)
        if not self.should_execute(node_id):
            return super(DefaultTaskSerializer, self).serialize(node_id)

        task = utils.traverse(
            self.task_template,
            TaskAttributesGenerator(deployment_info),
            self.get_formatter_context(deployment_info)
        )
        task.setdefault('parameters', {}).setdefault('cwd', '/')
        task.setdefault('fail_on_error', True)
        task.setdefault('task_name', 'none')
        for attr in self.hidden_attributes:
            task.pop(attr, None)
        return task

    def get_legacy_expression_context(self, node_uid=None):
        # Expression context for legacy parser
        return {
            'cluster': self.context.get_state(node_uid)['environment'],
            'settings': self.context.get_state(node_uid)
        }

    @staticmethod
    def get_formatter_context(deployment_info):
        return {
            'CLUSTER_ID': deployment_info['environment']['id'],
            'OPENSTACK_VERSION': deployment_info['openstack_version'],
            'MASTER_IP': settings.MASTER_IP,
            'CN_HOSTNAME': deployment_info['public_ssl']['hostname'],
            'DEPLOYMENT_INFO': deployment_info,
            'SETTINGS': settings
        }


class TasksSerializersFactory(object):
    factories = {
        consts.ORCHESTRATOR_TASK_TYPES.skipped: NoopTaskSerializer,
        consts.ORCHESTRATOR_TASK_TYPES.stage: NoopTaskSerializer
    }

    def __init__(self, context):
        self.context = context

    def create_serializer(self, task_template):
        serializer_class = self.factories.get(
            task_template['type'], DefaultTaskSerializer
        )
        return serializer_class(self.context, task_template)
