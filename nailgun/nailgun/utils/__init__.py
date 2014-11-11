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

import glob
import os
import string
import six
import yaml

from copy import deepcopy
from random import choice

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


def traverse(attributes, generator_class):
    """Traverse through attributes and replace values with
    generated ones where generators are provided.

    E.g.:
    'value': { 'generator': 'from_settings',
               'generator_arg' : 'MASTER_IP' }
    """
    def _helper(_obj):
        for key, val in six.iteritems(_obj):
            if isinstance(val, dict):
                if key == 'value' and 'generator' in val:
                    method = val['generator']
                    try:
                        generator = getattr(generator_class, method)
                    except AttributeError:
                        logger.error("Couldn't find generator %s.%s",
                                     generator_class, method)
                        raise
                    else:
                        _obj[key] = generator(val.get("generator_arg"))
                else:
                    _helper(_obj[key])

    # Copy attributes to make sure it won't be changed
    obj = deepcopy(attributes)

    if not isinstance(obj, dict):
        return obj

    _helper(obj)
    return obj


class AttributesGenerator(object):
    """Container class for producing different types of attributes
    """

    @staticmethod
    def password(arg=None):
        try:
            length = int(arg)
        except Exception:
            length = 8
        chars = string.letters + string.digits
        return u''.join([choice(chars) for _ in xrange(length)])

    @staticmethod
    def hexstring(arg=None):
        try:
            length = int(arg)
        except (ValueError, TypeError):
            length = 8
        chars = '0123456789abcdef'
        return u''.join([choice(chars) for _ in range(length)])

    @staticmethod
    def ip(arg=None):
        if str(arg) in ("admin", "master"):
            return settings.MASTER_IP
        return "127.0.0.1"

    @staticmethod
    def identical(arg=None):
        return str(arg)

    @staticmethod
    def from_settings(arg):
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
