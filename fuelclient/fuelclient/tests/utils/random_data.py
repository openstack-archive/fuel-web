# -*- coding: utf-8 -*-
#
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

import random
import string


def random_string(lenght, prefix='', postfix='', charset=None):
    """Returns a random string of the specified length

    :param length:  The length of the resulting string.
    :type lenght:   int.
    :param prefix:  Prefix for the random string.
    :type prefix:   str, default: ''.
    :param postfix: Postfix for the random string.
    :type postfix:  str, default ''.
    :param charset: A set of characters to use for building random strings.
    :type chartet:  Iterable object. Default: ASCII letters and digits.
    :return:        str

    """
    charset = charset or string.ascii_letters + string.digits
    base_length = lenght - (len(prefix) + len(postfix))

    base = ''.join([str(random.choice(charset)) for i in xrange(base_length)])

    return '{prefix}{base}{postfix}'.format(prefix=prefix,
                                            postfix=postfix,
                                            base=base)
