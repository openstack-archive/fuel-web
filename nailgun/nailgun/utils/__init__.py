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

import base64
import collections
import glob
import os
import re
import shutil
import string
import struct
import six
import time
import yaml

from copy import deepcopy
from itertools import chain
from random import choice

from six.moves import range
from six.moves import zip_longest

from uuid import uuid4

from nailgun.logger import logger
from nailgun.settings import settings


def reverse(name, kwargs=None):
    from nailgun.api.v1.urls import get_all_urls
    urls = get_all_urls()[0]
    urldict = dict(zip(urls[1::2], urls[::2]))
    url = urldict[name]
    urlregex = re.compile(url)
    for kwarg in urlregex.groupindex:
        if kwarg not in kwargs:
            raise KeyError("Invalid argument specified")
        url = re.sub(
            r"\(\?P<{0}>[^)]+\)".format(kwarg),
            str(kwargs[kwarg]),
            url,
            1
        )
    url = re.sub(r"\??\$", "", url)
    return "/api" + url


def remove_silently(path):
    """Removes an element from file system

    no matter if it's file, folder or symlink. Ignores OSErrors.

    :param path: path
    """
    try:
        if os.path.islink(path):
            os.unlink(path)
        elif os.path.isfile(path):
            os.remove(path)
        elif os.path.isdir(path):
            shutil.rmtree(path)
    except OSError as e:
        logger.exception(e)


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


def text_format(data, context):
    try:
        return data.format(**context)
    except Exception as e:
        raise ValueError("Cannot format {0}: {1}".format(data, e))


def text_format_safe(data, context):
    try:
        return data.format(**context)
    except Exception as e:
        logger.warning("Cannot format %s: %s. it will be used as is.",
                       data, six.text_type(e))
        return data


def traverse(data, formatter=None, formatter_context=None, keywords=None):
    """Traverse data.

    :param data: an input data to be traversed
    :param formatter_context: a dict to be passed into .format() for strings
    :param formatter: the text formatter, by default text_format will be used
    :param keywords: the dict where keys is name of keyword,
        value is callable to handle value of keyword.
        if original data contains key with name <keyword_name>_arg
        its value will be passed to callable as argument.
        for example:
        the keywords is {"generator": AttributeGenerator}

        data:
            generator: from_settings
            generator_arg: MASTER_IP

        the AttributeGenerator will be called with arguments:
            "from_settings", "MASTER_IP"

    :returns: a dict with traversed data
    """

    if formatter is None:
        formatter = text_format

    # check if keywords is specified and generate value if it is
    if isinstance(data, collections.Mapping) and keywords:
        for k in keywords:
            if k in data:
                arg_name = k + '_arg'
                try:
                    if arg_name in data:
                        return keywords[k](data[k], data[arg_name])
                    else:
                        return keywords[k](data[k])
                except Exception as e:
                    logger.error(
                        "Cannot evaluate expression - '%s' (%s), : %s",
                        data[k], data.get(arg_name), e
                    )
                    raise

    # we want to traverse in all levels, so dive in child mappings
    if isinstance(data, collections.Mapping):
        rv = {}
        for key, value in six.iteritems(data):
            # NOTE(ikalnitsky): regex node has python's formatting symbols,
            # so it fails if we try to format them. as a workaround, we
            # can skip them and do copy as is.
            if key != 'regex':
                rv[key] = traverse(
                    value, formatter, formatter_context, keywords
                )
            else:
                rv[key] = value
        return rv

    # format all strings with "formatter_context"
    elif isinstance(data, six.string_types) and formatter_context:
        return formatter(data, formatter_context)
    # we want to traverse all sequences also (lists, tuples, etc)
    elif isinstance(data, (list, tuple, set)):
        return type(data)(
            traverse(i, formatter, formatter_context, keywords)
            for i in data
        )

    # just return value as is for all other cases
    return data


class AttributesGenerator(object):

    @classmethod
    def password(cls, arg=None):
        try:
            length = int(arg)
        except Exception:
            length = 24
        chars = string.letters + string.digits
        return u''.join([choice(chars) for _ in xrange(length)])

    @classmethod
    def hexstring(cls, arg=None):
        try:
            length = int(arg)
        except (ValueError, TypeError):
            length = 8
        chars = '0123456789abcdef'
        return u''.join([choice(chars) for _ in range(length)])

    @classmethod
    def ip(cls, arg=None):
        if str(arg) in ("admin", "master"):
            return settings.MASTER_IP
        return "127.0.0.1"

    @classmethod
    def identical(cls, arg=None):
        return str(arg)

    @classmethod
    def from_settings(cls, arg):
        return getattr(settings, arg)

    @classmethod
    def uuid4(cls, arg=None):
        return uuid4()

    @classmethod
    def cephx_key(cls, arg=None):
        """Returns a cephx auth key.

        this is taken verbatim from
        https://github.com/ceph/ceph-deploy/blob/master/ceph_deploy/new.py#L21-30

        :returns: string (base64 encoded binary) usable as a cephx auth key
        """

        key = os.urandom(16)
        header = struct.pack(
            '<hiih',
            1,                 # le16 type: CEPH_CRYPTO_AES
            int(time.time()),  # le32 created: seconds
            0,                 # le32 created: nanoseconds,
            len(key),          # le16: len(key)
        )
        return base64.b64encode(header + key)

    @classmethod
    def evaluate(cls, func, arg=None):
        return getattr(cls, func)(arg)


def camel_to_snake_case(name):
    """Convert camel case format into snake case
    """
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def compact(array):
    """Remove all falsy items from array
    """
    return [x for x in array if x not in [None, '', False]]


def flatten(array):
    """Flattens a nested array with one nesting depth
    """
    # TODO: implement for nesting with any depth
    check = lambda x: x if isinstance(x, list) else [x]

    return list(chain.from_iterable(check(x) for x in array))


def grouper(iterable, n, fillvalue=None):
    """Collect data into fixed-length chunks or blocks
    """
    args = [iter(iterable)] * n
    return zip_longest(*args, fillvalue=fillvalue)


def join_range(r):
    """Converts (1, 2) -> "1:2"
    """
    return ":".join(map(str, r)) if r else None


def get_lines(text):
    """Returns all non-empty lines in input string
    """
    return list(six.moves.filter(bool, text.splitlines()))


def dict_update(target, patch, level=None):
    """Updates dict recursively.

    :param target: the target dict, will be update inplace
    :param patch: the modifications, that will be applied to target
    :param level: how deeper the update will be applied
                  (None means not limited)
    """
    for k, v in six.iteritems(patch):
        if isinstance(v, dict):
            if level is None or level > 1:
                dict_update(
                    target.setdefault(k, {}),
                    v,
                    level if level is None else level - 1
                )
            else:
                target.setdefault(k, {}).update(v)
        else:
            target[k] = v


def parse_bool(value):
    """
    Returns boolean value from string representation.

    Function returns ``True`` for ``"1", "t", "true"`` values
    and ``False`` for ``"0", "f", "false"``.
    Otherwise raises ValueError.

    :param str value: string representation of boolean value
    :rtype: bool
    :raises ValueError: if the value cannot be converted to bool
    """
    value = value.lower()
    if value in ('1', 't', 'true'):
        return True
    elif value in ('0', 'f', 'false'):
        return False
    else:
        raise ValueError('Invalid value: {0}'.format(value))

