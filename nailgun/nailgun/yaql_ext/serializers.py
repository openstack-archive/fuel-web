#    Copyright 2016 Mirantis, Inc.
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


from oslo_serialization import jsonutils
import yaml
from yaql.language import specs
from yaql.language import yaqltypes


@specs.method
@specs.inject('func', yaqltypes.Delegate('#finalize'))
def to_yaml(func, receiver):
    return yaml.safe_dump(func(receiver))


@specs.method
@specs.inject('func', yaqltypes.Delegate('#finalize'))
def to_json(func, receiver):
    return jsonutils.dumps(func(receiver))


def register(context):
    context.register_function(to_yaml)
    context.register_function(to_json)
