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
from operator import attrgetter

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

    def action_func(self, params):
        self.serializer = Serializer.from_params(params)
        if is_list_of_instances(self.flag_func_map, tuple):
            for predicate, argument_checks, func in self.flag_func_map:
                if isinstance(predicate, str):
                    predicate = attrgetter(predicate)
                if predicate and predicate(params):
                    if argument_checks is None:
                        func(params)
                        break
                    elif not isinstance(argument_checks, tuple):
                        argument_checks = (argument_checks,)
                    for check in argument_checks:
                        if not check(params):
                            raise ArgumentException(
                                "{0} required!".format(
                                    quote_and_join(
                                        "--" + arg for arg in check.params
                                    )
                                )
                            )
                    func(params)
                    break
                elif predicate is None:
                    func(params)
        elif is_list_of_instances(self.flag_func_map, str):
            for func_name in self.flag_func_map:
                if getattr(params, func_name):
                    getattr(self, func_name)(params)


def attrcheck(method):
    def outer(*args):
        def func(params):
            return method(getattr(params, arg) for arg in args)
        func.params = args
        return func
    return outer
