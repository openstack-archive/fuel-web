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
Network template
"""

import re
import six


class BaseTemplate(object):

    idpattern = None        # a regex pattern of the identifier
    braces = (None, None)   # a pair of open/closing braces

    def __init__(self, template):
        self.template = template
        self.pattern = re.compile(
            r'{0}\s*(?P<id>{2})\s*{1}'.format(
                self.braces[0], self.braces[1], self.idpattern
            ),
            re.IGNORECASE | re.VERBOSE)

    def substitute(self, data={}, **kwargs):
        def convert(mo):
            key = mo.group('id')
            val = kwargs[key] if key in kwargs else data[key]
            return six.text_type(val)
        return self.pattern.sub(convert, self.template)

    def safe_substitute(self, data={}, **kwargs):
        def convert(mo):
            key = mo.group('id')
            if key in kwargs:
                val = kwargs[key]
            elif key in data:
                val = data[key]
            else:
                val = mo.group()
            return six.text_type(val)
        return self.pattern.sub(convert, self.template)


class NetworkTemplate(BaseTemplate):
    """NetworkTemplate object provides string substitution

    NetworkTemplate substitutes <% key %> to value
    for key=value
    Spaces inside <%...%> block are ignored

    Example:
    template = NetworkTemplate("a: <%a%> b: <% b %>")
    template.safe_substitute(a='aaa', b='bbb')
    -> "a: aaa b: bbb"
    """

    idpattern = r'[_a-z][_a-z0-9]*'
    braces = ('<%', '%>')
