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

from fuelclient.cli.error import ArgumentException
from fuelclient.cli.formatting import quote_and_join
from fuelclient.cli.serializers import Serializer


def is_list_of_instances(list_of_objects, _type):
    return all(map(
        lambda x: isinstance(x, _type),
        list_of_objects))


class Action(object):
    """Action class must have following attributes
    action_name, action_func, examples
    """
    action_name = None
    flag_func_map = None
    flag_func_list = None

    def action_func(self, params):
        self.serializer = Serializer.from_params(params)
        if self.flag_func_map is not None:
            for flag, method in self.flag_func_map:
                if flag is None or getattr(params, flag):
                    method(params)
                    break
        else:
            for func_name in self.flag_func_list:
                if getattr(params, func_name):
                    getattr(self, func_name)(params)


def check_all(*args):
    def wrap(f):
        def wrapped_f(self, params):
            if all(getattr(params, _arg) for _arg in args):
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
    return wrap


def check_any(*args):
    def wrap(f):
        def wrapped_f(self, params):
            if any(getattr(params, _arg) for _arg in args):
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
    return wrap
