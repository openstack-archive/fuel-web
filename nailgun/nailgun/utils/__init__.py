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

import collections
import glob
import os
import re
import string
import six
import yaml

from copy import deepcopy
from itertools import chain
from random import choice

from six.moves import zip_longest

from nailgun.logger import logger
from nailgun.settings import settings


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


def traverse(data, generator_class, formatter_context=None):
    """Traverse data.

    :param data: an input data to be traversed
    :param generator_class: a generator class to be used
    :param formatter_context: a dict to be passed into .format() for strings
    :returns: a dict with traversed data
    """

    # generate value if generator is specified
    if isinstance(data, collections.Mapping) and 'generator' in data:
         try:
             generator = getattr(generator_class, data['generator'])
             return generator(data.get('generator_arg'))
         except AttributeError:
             logger.error('Attribute error: %s', data['generator'])
             raise

    # we want to traverse in all levels, so dive in child mappings
    elif isinstance(data, collections.Mapping):
        rv = {}
        for key, value in six.iteritems(data):
            # NOTE(ikalnitsky): regex node has python's formatting symbols,
            # so it fails if we try to format them. as a workaround, we
            # can skip them and do copy as is.
            if key != 'regex':
                rv[key] = traverse(value, generator_class, formatter_context)
            else:
                rv[key] = value
        return rv

    # format all strings with "formatter_context"
    elif isinstance(data, six.string_types) and formatter_context:
        return data.format(**formatter_context)

    # we want to traverse all sequences also (lists, tuples, etc)
    elif isinstance(data, (list, tuple)):
        return type(data)(
            (traverse(i, generator_class, formatter_context) for i in data))

    # just return value as is for all other cases
    return data


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


def extract_env_version(release_version):
    """Returns environment version based on release version.

    A release version consists of 'OSt' and 'MOS' versions: '2014.1.1-5.0.2'
    so we need to extract 'MOS' version and returns it as result.

    .. todo:: [ikalnitsky] think about introducing a special field in release

    :param release_version: a string which represents a release version
    :returns: an environment version
    """
    separator = '-'

    # unfortunately, Fuel 5.0 didn't has an env version in release_version
    # so we need to handle that special case
    if release_version == '2014.1':
        return '5.0'

    # we need to extract a second part since it's what we're looking for
    return release_version.split(separator)[1]


def get_fuel_release_versions(path_mask):
    """Returns release versions from files match to path_mask

    :param path_mask: mask of path to release version files
    :type path_mask: string
    :returns: dicts with file names as keys and release
    versions info as values
    """

    result = {}
    for fl in glob.glob(path_mask):
        with open(fl, "r") as release_version:
            file_name = os.path.splitext(os.path.basename(fl))[0]
            try:
                result[file_name] = yaml.load(release_version.read())
            except Exception as exc:
                logger.warning(
                    u"Failed to load release version "
                    "info from '{0}': {1}".format(
                        fl,
                        six.text_type(exc)
                    )
                )
    return result


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
