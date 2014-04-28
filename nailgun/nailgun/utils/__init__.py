#    Copyright 2013 Mirantis, Inc.
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

import string

from copy import deepcopy
from random import choice

from nailgun.logger import logger
from nailgun.settings import settings
from nailgun.utils.expression_parser import parser


def dict_merge(a, b):
    '''recursively merges dict's. not just simple a['key'] = b['key'], if
    both a and bhave a key who's value is a dict then dict_merge is called
    on both values and the result stored in the returned dictionary.
    '''
    if not isinstance(b, dict):
        return deepcopy(b)
    result = deepcopy(a)
    for k, v in b.iteritems():
        if k in result and isinstance(result[k], dict):
            result[k] = dict_merge(result[k], v)
        else:
            result[k] = deepcopy(v)
    return result


def traverse(cdict, generator_class):
    new_dict = {}
    if cdict:
        for i, val in cdict.iteritems():
            if isinstance(val, (str, unicode, int, float)):
                new_dict[i] = val
            elif isinstance(val, dict) and "generator" in val:
                try:
                    generator = getattr(
                        generator_class,
                        val["generator"]
                    )
                except AttributeError:
                    logger.error("Attribute error: %s" % val["generator"])
                    raise
                else:
                    new_dict[i] = generator(val.get("generator_arg"))
            else:
                new_dict[i] = traverse(val, generator_class)
    return new_dict


def evaluate_expression(expression, models=None):
    return parser.parse(expression)


class AttributesGenerator(object):
    @classmethod
    def password(cls, arg=None):
        try:
            length = int(arg)
        except Exception:
            length = 8
        chars = string.letters + string.digits
        return u''.join([choice(chars) for _ in xrange(length)])

    @classmethod
    def ip(cls, arg=None):
        if str(arg) in ("admin", "master"):
            return settings.MASTER_IP
        return "127.0.0.1"

    @classmethod
    def identical(cls, arg=None):
        return str(arg)
