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

from functools import wraps
import sys
import urllib2


def print_error(message):
    sys.stderr.write(message + "\n")
    exit(1)


class FuelClientException(Exception):
    pass


class DeployProgressError(FuelClientException):
    pass


class ArgumentException(FuelClientException):
    pass


class ActionException(FuelClientException):
    pass


class ParserException(FuelClientException):
    pass


def handle_exceptions(exc):
    if isinstance(exc, urllib2.HTTPError):
        error_body = exc.read()
        print_error("{0} {1}".format(
            exc,
            "({0})".format(error_body or "")
        ))
    elif isinstance(exc, urllib2.URLError):
        print_error("Can't connect to Nailgun server!")
    elif isinstance(exc, FuelClientException):
        print_error(exc.message)
    else:
        raise


def exceptions_decorator(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            handle_exceptions(exc)
    return wrapper
