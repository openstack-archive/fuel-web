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

from yaql.language import specs
from yaql.language import yaqltypes

from nailgun.logger import logger
from nailgun.utils import datadiff


_UNDEFINED = object()


@specs.parameter('expression', yaqltypes.Lambda())
def get_new(expression, context):
    return expression(context['$new'])


@specs.parameter('expression', yaqltypes.Lambda())
def get_old(expression, context):
    try:
        return expression(context['$old'])
    except Exception as e:
        # exception in evaluation on old data interprets as data changed
        logger.debug('Cannot evaluate expression on old data: %s', e)
        return _UNDEFINED


@specs.parameter('expression', yaqltypes.Lambda())
def changed(expression, context):
    return get_new(expression, context) != get_old(expression, context)


@specs.parameter('expression', yaqltypes.Lambda())
def added(expression, context):
    new_data = get_new(expression, context)
    old_data = get_old(expression, context)
    if old_data is _UNDEFINED:
        return new_data
    return datadiff.diff(old_data, new_data).added


@specs.parameter('expression', yaqltypes.Lambda())
def deleted(expression, context):
    new_data = get_new(expression, context)
    old_data = get_old(expression, context)
    if old_data is not _UNDEFINED:
        return datadiff.diff(old_data, new_data).deleted


@specs.method
@specs.inject('finalizer', yaqltypes.Delegate('#finalize'))
def is_undef(finalizer, receiver):
    return finalizer(receiver) is _UNDEFINED


def register(context):
    context.register_function(get_new, name='new')
    context.register_function(get_old, name='old')
    context.register_function(changed)
    context.register_function(added)
    context.register_function(deleted)
    context.register_function(is_undef)
