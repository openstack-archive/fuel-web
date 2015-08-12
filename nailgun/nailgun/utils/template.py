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
Utils for templates
"""

from string import Template


class NetworkTemplate(Template):
    """NetworkTemplate object provides string substitution
    NetworkTemplate substitutes <% key %> to value
    for key=value
    Spaces inside <%...%> block are ignored

    Example:
    template = NetworkTemplate("a: <%a%> b: <% b %>")
    template.safe_substitute(a='aaa', b='bbb')
    -> "a: aaa b: bbb"
    """

    delimiter = '<%'
    pattern = r"""
    <%\s*(?:
      (?P<escaped><%\s*)                 |
      (?P<named>[_a-z][_a-z0-9]*)\s*%>   |
      (?P<braced>[_a-z][_a-z0-9]*)\s*%>  |
      (?P<invalid>)
    )
    """
