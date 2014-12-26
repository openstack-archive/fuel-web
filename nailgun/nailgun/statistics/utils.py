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

import os
import six

from contextlib import contextmanager

from nailgun.logger import logger


@contextmanager
def set_proxy(proxy):
    """Replace http_proxy environment variable for the scope
    of context execution. After exit from context old proxy value
    (if any) is restored

    :param proxy: - proxy url
    """
    proxy_old_value = None

    if os.environ.get("http_proxy"):
        proxy_old_value = os.environ["http_proxy"]
        logger.warning("http_proxy variable is already set with "
                       "value: {0}. Change to {1}. Old value "
                       "will be restored after exit from script's "
                       "execution context"
                       .format(proxy_old_value, proxy))

    os.environ["http_proxy"] = proxy

    try:
        yield
    except Exception as e:
        logger.exception("Error while interacting with "
                         "OpenStack api. Details: {0}"
                         .format(six.text_type(e)))
    finally:
        if proxy_old_value:
            logger.info("Restoring old value for http_proxy")
            os.environ["http_proxy"] = proxy_old_value
        else:
            logger.info("Deleting set http_proxy environment variable")
            del(os.environ["http_proxy"])


class _Missing(object):
    def __repr__(self):
        return "no value"


_missing = _Missing()


class cached_property(object):
    """Inspired by werkzeug progect's code:
    https://github.com/mitsuhiko/werkzeug/blob/master/werkzeug/utils.py#L35-L73

    Quotation from the class' documentation:
        'A decorator that converts a function into a lazy property.  The
    function wrapped is called the first time to retrieve the result
    and then that calculated result is used the next time you access
    the value::
        class Foo(object):
            @cached_property
            def foo(self):
                # calculate something important here
                return 42
    The class has to have a `__dict__` in order for this property to
    work.'
    """
    def __init__(self, func, name=None, doc=None):
        self.__name__ = name or func.__name__
        self.__module__ = func.__module__
        self.__doc__ = doc or func.__doc__
        self.func = func

    def __get__(self, obj, type=None):
        if obj is None:
            return self
        value = obj.__dict__.get(self.__name__, _missing)
        if value is _missing:
            value = self.func(obj)
            obj.__dict__[self.__name__] = value
        return value
