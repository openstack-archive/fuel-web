#    Copyright 2014 Mirantis, Inc.
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

import re
import six
from StringIO import StringIO


def get_body_from_env(env):
    """Exctracts request body from wsgi
    environment variable
    """
    content_length = env.get('CONTENT_LENGTH', 0)
    if content_length == '':
        content_length = 0
    length = int(content_length)
    body = ''

    if length != 0:
        body = env['wsgi.input'].read(length)
        env['wsgi.input'] = StringIO(body)

    return body


def compile_mapping_keys(mapping):
    return dict(
        [(re.compile(k), v)
         for k, v in six.iteritems(mapping)]
    )


def get_group_from_matcher(matcher_obj, string_to_match, group_name):
    """Returns value corresponding to given group_name if it is present in
    matcher_obj
    """
    matched = matcher_obj.match(string_to_match)
    if matched:
        groups_dictionary = matched.groupdict()
        if groups_dictionary.get(group_name):
            return groups_dictionary[group_name]

    return None
