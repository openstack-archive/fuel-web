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

from fuelclient.cli.error import ArgumentException
from fuelclient.cli.formatting import quote_and_join
from fuelclient.cli.serializers import Serializer
from fuelclient.client import APIClient


class Action(object):
    """Action class generalizes logic of action execution
    method action_func  - entry point of parser

    """
    def __init__(self):
        # Mapping of flags to methods
        self.flag_func_map = None
        self.serializer = Serializer()

    def action_func(self, params):
        """Entry point for all actions subclasses
        """
        APIClient.debug_mode(debug=params.debug)
        self.serializer = Serializer.from_params(params)
        if self.flag_func_map is not None:
            for flag, method in self.flag_func_map:
                if flag is None or getattr(params, flag):
                    method(params)
                    break

    @property
    def examples(self):
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


def wrap(method, args, f):
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
    return partial(wrap, all, args)


def check_any(*args):
    return partial(wrap, any, args)
