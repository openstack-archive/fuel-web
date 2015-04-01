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

"""
Classes for checking data restrictions
"""

import re
import six

from nailgun.errors import errors
from nailgun.expression import Expression
from nailgun.utils import camel_to_snake_case


class RestrictionMixin(object):
    """Mixin which extend nailgun objects with restriction
    processing functionality
    """

    @classmethod
    def check_restrictions(cls, models, restrictions, action=None):
        """Check if attribute satisfied restrictions

        :param models: objects which represent models in restrictions
        :type models: dict
        :param restrictions: list of restrictions to check
        :type restrictions: list
        :param action: filtering restrictions by action key
        :type action: string
        :returns: dict -- object with 'result' as number and 'message' as dict
        """
        satisfied = []

        if restrictions:
            expened_restrictions = map(
                cls._expand_restriction, restrictions)
            # Filter by action
            if action:
                filterd_by_action_restrictions = filter(
                    lambda item: item.get('action') == action,
                    expened_restrictions)
            else:
                filterd_by_action_restrictions = expened_restrictions[:]
            # Filter which restriction satisfied condition
            satisfied = filter(
                lambda item: Expression(
                    item.get('condition'), models).evaluate(),
                filterd_by_action_restrictions)

        return {
            'result': bool(satisfied),
            'message': '. '.join([item.get('message') for item in
            satisfied if item.get('message')])
        }

    @staticmethod
    def _expand_restriction(restriction):
        """Get restriction in different formats like string, short
        or long dict formats and return in one canonical format

        :param restriction: restriction object
        :type restriction: string|dict
        :returns: dict -- restriction object in canonical format:
                    {
                        'action': 'enable|disable|hide|none'
                        'condition': 'value1 == value2',
                        'message': 'value1 shouldn't equal value2'
                    }
        """
        result = {
            'action': 'disable'
        }

        if isinstance(restriction, six.string_types):
            result['condition'] = restriction
        elif isinstance(restriction, dict):
            if 'condition' in restriction:
                result.update(restriction)
            else:
                result['condition'] = list(restriction)[0]
                result['message'] = list(restriction.values())[0]
        else:
            raise errors.InvalidData('Invalid restriction format')

        return result


class AttributesRestriction(RestrictionMixin):

    @classmethod
    def check_data(cls, models, data):
        """Check cluster attributes data

        :param models: objects which represent models in restrictions
        :type models: dict
        :param data: cluster attributes object
        :type data: list|dict
        :retruns: func -- generator which produces errors
        """
        def find_errors(data=data):
            """Generator which traverses through cluster attributes tree
            checks restrictions for attributes and values for correctness
            with regex
            """
            if isinstance(data, dict):
                restr = cls.check_restrictions(
                    models, data.get('restrictions', []))
                if restr.get('result'):
                    # TODO(apopovych): handle restriction message
                    return
                else:
                    attr_regex = data.get('regex', {})
                    if attr_regex:
                        pattern = re.compile(attr_regex.get('source'))
                        if not pattern.match(data.get('value')):
                            yield attr_regex.get('error')
                    for key, value in six.iteritems(data):
                        if key not in ['restrictions', 'regex']:
                            for err in find_errors(value):
                                yield err
            elif isinstance(data, list):
                for item in data:
                    for err in find_errors(item):
                        yield err

        return list(find_errors())


class VmwareAttributesRestriction(RestrictionMixin):

    @classmethod
    def check_data(cls, models, metadata, data):
        """Check cluster vmware attributes data

        :param models: objects which represent models in restrictions
        :type models: dict
        :param metadata: vmware attributes metadata object
        :type metadata: list|dict
        :param data: vmware attributes data(value) object
        :type data: list|dict
        :retruns: func -- generator which produces errors
        """
        root_key = camel_to_snake_case(cls.__name__)

        def find_errors(metadata=metadata, path_key=root_key):
            """Generator for vmware attributes errors which for each
            attribute in 'metadata' gets relevant values from vmware
            'value' and checks them with restrictions and regexs
            """
            if isinstance(metadata, dict):
                restr = cls.check_restrictions(
                    models, metadata.get('restrictions', []))
                if restr.get('result'):
                    # TODO(apopovych): handle restriction message?
                    return
                else:
                    for mkey, mvalue in six.iteritems(metadata):
                        if mkey == 'name':
                            value_path = path_key.replace(
                                root_key, '').replace('.fields', '')
                            values = cls._get_values(value_path, data)
                            attr_regex = metadata.get('regex', {})
                            if attr_regex:
                                pattern = re.compile(attr_regex.get('source'))
                                for value in values():
                                    if not pattern.match(value):
                                        yield attr_regex.get('error')
                        for err in find_errors(
                                mvalue, '.'.join([path_key, mkey])):
                            yield err
            elif isinstance(metadata, list):
                for i, item in enumerate(metadata):
                    current_key = item.get('name') or str(i)
                    for err in find_errors(
                            item, '.'.join([path_key, current_key])):
                        yield err

        return list(find_errors())

    @classmethod
    def _get_values(cls, path, data):
        """Generator for all values from data selected by given path

        :param path: path to all releted values
        :type path: string
        :param data: vmware attributes value
        :type data: list|dict
        """
        keys = path.split('.')
        key = keys[-1]

        def find(data=data):
            if isinstance(data, dict):
                for k, v in six.iteritems(data):
                    if k == key:
                        yield v
                    elif k in keys:
                        for result in find(v):
                            yield result
            elif isinstance(data, list):
                for d in data:
                    for result in find(d):
                        yield result

        return find
