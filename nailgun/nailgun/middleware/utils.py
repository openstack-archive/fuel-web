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

import copy
import re
import six
from StringIO import StringIO


def get_body_from_env(env):
    content_length = env.get('CONTENT_LENGTH', 0)
    if content_length == '':
        content_length = 0
    length = int(content_length)
    body = ''

    if length != 0:
        body = env['wsgi.input'].read(length)
        env['wsgi.input'] = StringIO(body)

    return env, body


def compile_mapping_keys(mapping):
    compiled_mapping = copy.deepcopy(mapping)
    for key, value in six.iteritems(mapping):
        comp_key = re.compile(key)
        compiled_mapping[comp_key] = value

    return mapping
