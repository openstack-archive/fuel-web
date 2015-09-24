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

from nailgun.utils import dict_merge


class UnresolvableConflict(ValueError):
    pass


@six.add_metaclass(abc.ABCMeta)
class MergePolicy(object):
    """class that provides functional
    to plugins attributes with origin.
    """

    @abc.abstractmethod
    def apply_patch(self, target, patch):
        """applies patch to target."""


class NetworkRoleMergePolicy(MergePolicy):
    def __init__(self):
        self.mergeable = frozenset(('vip',))

    def apply_patch(self, target, patch):
        """try to apply patch to target,
        resolve conflicts according to known about fields,
        that can be merged.
        """

        target_props = target['properties']
        patch_props = patch['properties']

        conflict = set(target_props) & set(patch_props)

        # exclude fields that has same value
        for k in (conflict - self.mergeable):
            if target_props[k] != patch_props[k]:
                raise UnresolvableConflict(
                    "Cannot merge field {0}".format(k)
                )
            conflict.remove(k)

        if conflict <= self.mergeable:
            for k in conflict:
                target_value = target_props[k]
                patch_value = patch_props[k]
                if type(target_value) is not type(patch_value):
                    raise UnresolvableConflict(
                        "Cannot merge {0} and {1} for attribute {2}"
                        .format(type(target_value), type(patch_value), k)
                    )
                if isinstance(target_value, dict):
                    target_props[k] = dict_merge(target_value, patch_value)
                elif isinstance(target_value, list):
                    target_value.extend(patch_value)
                else:
                    target_props[k] = patch_value
