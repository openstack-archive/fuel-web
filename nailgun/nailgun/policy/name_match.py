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
import re
import six


@six.add_metaclass(abc.ABCMeta)
class NameMatchingPolicy(object):
    @abc.abstractmethod
    def match(self, name):
        """Tests that name is acceptable.

        :param name: the name to test
        :type name: str
        :returns: True if yes otherwise False
        """

    @staticmethod
    def create(pattern):
        """Makes name matching policy.

        the string wrapped with '/' treats as pattern
        '/abc/' - pattern
        'abc' - the string for exact match

        :param pattern: the pattern to match
        :return: the NameMatchPolicy instance
        """
        if pattern.startswith("/") and pattern.endswith("/"):
            return PatternMatchingPolicy(pattern[1:-1])
        return ExactMatchingPolicy(pattern)


class ExactMatchingPolicy(NameMatchingPolicy):
    """Tests that name exact match to argument."""

    def __init__(self, name):
        """Initializes.

        :param name: the name to match
        """
        self.name = name

    def match(self, name):
        return self.name == name


class PatternMatchingPolicy(NameMatchingPolicy):
    """Tests that pattern matches to argument."""

    def __init__(self, pattern):
        self.pattern = re.compile(pattern)

    def match(self, name):
        return self.pattern.search(name)
