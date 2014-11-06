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

from functools import partial
from functools import wraps
from itertools import imap
import os

from fuelclient.cli.error import ArgumentException
from fuelclient.cli.formatting import quote_and_join
from fuelclient.cli.serializers import Serializer
from fuelclient.client import APIClient


class Action(object):
    """Action class generalizes logic of action execution
    method action_func  - entry point of parser with parsed arguments

    flag_func_map - is tuple of pairs ("flag", self.some_method) where
    "flag" is name of argument which causes "some_method" to be called.
    None is used as "flag" when method will be called without any flag.

    serializer - is Serializer class instance which supposed to be the
    only way to read and write to output or file system.

    args - tuple of function calls of functions from arguments module,
    is a manifest of all arguments used in action, and is used to initialize
    argparse subparser of that action.
    """
    def __init__(self):
        # Mapping of flags to methods
        self.flag_func_map = None
        self.serializer = Serializer()

    def action_func(self, params):
        """Entry point for all actions subclasses
        """
        APIClient.debug_mode(debug=params.debug)
        if getattr(params, 'user') and getattr(params, 'password'):
            APIClient.user = params.user
            APIClient.password = params.password
            APIClient.initialize_keystone_client()

        self.serializer = Serializer.from_params(params)
        if self.flag_func_map is not None:
            for flag, method in self.flag_func_map:
                if flag is None or getattr(params, flag):
                    method(params)
                    break

    @property
    def examples(self):
        """examples property is concatenation of __doc__ strings from
        methods in child action classes, and is added as epilog of help
        output
        """
        methods_with_docs = set(
            method
            for _, method in self.flag_func_map
        )
        return "Examples:\n\n" + \
               "\n".join(
                   imap(
                       lambda method: (
                           "\t" + method.__doc__.replace("\n    ", "\n")
                       ),
                       methods_with_docs
                   )
               ).format(
                   action_name=self.action_name
               )

    def full_path_directory(self, directory, base_name):
        full_path = os.path.join(directory, base_name)
        if not os.path.exists(full_path):
            os.mkdir(full_path)
        return full_path

    def default_directory(self, directory=None):
        return os.path.abspath(os.curdir if directory is None else directory)


def wrap(method, args, f):
    """wrap - is second order function, purpose of which is to
    generalize argument checking for methods in actions in form
    of decorator with arguments.

    'check_all' and 'check_any' are partial function of wrap.
    """
    @wraps(f)
    def wrapped_f(self, params):
        if method(getattr(params, _arg) for _arg in args):
            return f(self, params)
        else:
            raise ArgumentException(
                "{0} required!".format(
                    quote_and_join(
                        "--" + arg for arg in args
                    )
                )
            )
    return wrapped_f


def check_all(*args):
    """check_all - decorator with arguments, which checks that
    all arguments are given before running action method, if
    not all arguments are given, it raises an ArgumentException.
    """
    return partial(wrap, all, args)


def check_any(*args):
    """check_any - decorator with arguments, which checks that
    at least one arguments is given before running action method,
    if no arguments were given, it raises an ArgumentException.
    """
    return partial(wrap, any, args)
