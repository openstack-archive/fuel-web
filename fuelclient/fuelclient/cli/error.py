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
from keystoneclient.exceptions import Unauthorized
import sys
import urllib2


def exit_with_error(message):
    """exit_with_error - writes message to stderr and exits with exit code 1.
    """
    sys.stderr.write(message + "\n")
    exit(1)


class FuelClientException(Exception):
    """Base Exception for Fuel-Client

    All child classes must be instantiated before raising.
    """
    def __init__(self, *args, **kwargs):
        super(FuelClientException, self).__init__(*args, **kwargs)
        self.message = args[0]


class ServerDataException(FuelClientException):
    """ServerDataException - must be raised when
    data returned from server cannot be processed by Fuel-Client methods.
    """


class DeployProgressError(FuelClientException):
    """DeployProgressError - must be raised when
    deployment process interrupted on server.
    """


class ArgumentException(FuelClientException):
    """ArgumentException - must be raised when
    incorrect arguments inputted through argparse or some function.
    """


class ActionException(FuelClientException):
    """ActionException - must be raised when
    though arguments inputted to action are correct but they contradict
    to logic in action.
    """


class ParserException(FuelClientException):
    """ParserException - must be raised when
    some problem occurred in process of argument parsing,
    in argparse extension or in Fuel-Client Parser submodule.
    """


def handle_exceptions(exc):
    """handle_exceptions - exception handling manager.
    """
    if isinstance(exc, urllib2.HTTPError):
        error_body = exc.read()
        exit_with_error("{0} {1}".format(
            exc,
            "({0})".format(error_body or "")
        ))
    elif isinstance(exc, urllib2.URLError):
        exit_with_error("""
        Can't connect to Nailgun server!
        Please modify "SERVER_ADDRESS" and "LISTEN_PORT"
        in the file /etc/fuel/client/config.yaml""")
    elif isinstance(exc, Unauthorized):
        exit_with_error("""
        Unauthorized: need authentication!
        Please provide user and password via client --os-username --os-password
        or modify "KEYSTONE_USER" and "KEYSTONE_PASS" in
        /etc/fuel/client/config.yaml""")
    elif isinstance(exc, FuelClientException):
        exit_with_error(exc.message)
    else:
        raise


def exceptions_decorator(func):
    """exceptions_decorator - is decorator which intercepts exceptions and
    redirects them to handle_exceptions.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            handle_exceptions(exc)
    return wrapper
