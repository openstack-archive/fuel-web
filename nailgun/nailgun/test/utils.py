# -*- coding: utf-8 -*-
#
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

import random
import six
import string

import mock


def random_string(lenght, charset=None):
    """Returns a random string of the specified length

    :param length:  The length of the resulting string.
    :type lenght:   int.
    :param charset: A set of characters to use for building random strings.
    :type charset:  Iterable object. Default: ASCII letters and digits.
    :return:        str

    """
    charset = charset or string.ascii_letters + string.digits

    return ''.join([str(random.choice(charset))
                    for i in six.moves.range(lenght)])


def make_mock_extensions(names=('ext1', 'ext2')):
    mocks = []
    for name in names:
        # NOTE(eli): since 'name' is reserved word
        # for mock constructor, we should assign
        # name explicitly
        ex_m = mock.MagicMock()
        ex_m.name = name
        ex_m.provides = ['method_call']
        mocks.append(ex_m)

    return mocks
