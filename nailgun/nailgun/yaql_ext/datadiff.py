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
from yaql.language import utils as yaqlutils
from yaql.language import yaqltypes

from nailgun.logger import logger
from nailgun.utils import datadiff


_UNDEFINED = object()


@specs.parameter('expression', yaqltypes.Lambda())
def get_new(expression, context):
    return expression(context['$%new'])


@specs.parameter('expression', yaqltypes.Lambda())
def get_old(expression, context):
    try:
        return expression(context['$%old'])
    except Exception as e:
        # exception in evaluation on old data interprets
        # we return special sentinel to check that data was actually changed
        # we cannot use empty object here, because new data can be empty
        # as well, and in this case there is no chance to detect
        # data was changed or not
        logger.debug('Cannot evaluate expression on old data: %s', e)
        return _UNDEFINED


@specs.parameter('expression', yaqltypes.Lambda())
@specs.inject('finalizer', yaqltypes.Delegate('#finalize'))
def decreased_roles(finalizer, expression, context, *roles):
    def counter(data, roles):
        return sum(data.count(role) for role in roles)
    new_data = finalizer(get_new(expression, context))
    old_data = finalizer(get_old(expression, context))
    if old_data == _UNDEFINED:
        return True
    return counter(new_data, roles) < counter(old_data, roles)


@specs.parameter('expression', yaqltypes.Lambda())
@specs.inject('finalizer', yaqltypes.Delegate('#finalize'))
def changed(finalizer, expression, context):
    new_data = finalizer(get_new(expression, context))
    old_data = finalizer(get_old(expression, context))
    return new_data != old_data


@specs.parameter('expressions', yaqltypes.Lambda())
@specs.inject('finalizer', yaqltypes.Delegate('#finalize'))
def changed_all(finalizer, context, *expressions):
    return all(changed(finalizer, exp, context) for exp in expressions)


@specs.parameter('expressions', yaqltypes.Lambda())
@specs.inject('finalizer', yaqltypes.Delegate('#finalize'))
def changed_any(finalizer, context, *expressions):
    return any(changed(finalizer, exp, context) for exp in expressions)


def get_limited_if_need(data, engine):
    if (yaqlutils.is_iterable(data) or yaqlutils.is_sequence(data) or
            isinstance(data, (yaqlutils.MappingType, yaqlutils.SetType))):
        return yaqlutils.limit_iterable(data, engine)
    return data


@specs.parameter('expression', yaqltypes.Lambda())
def added(expression, context, engine):
    new_data = get_limited_if_need(get_new(expression, context), engine)
    old_data = get_limited_if_need(get_old(expression, context), engine)
    if old_data is _UNDEFINED:
        return new_data
    return datadiff.diff(old_data, new_data).added


@specs.parameter('expression', yaqltypes.Lambda())
def deleted(expression, context, engine):
    new_data = get_limited_if_need(get_new(expression, context), engine)
    old_data = get_limited_if_need(get_old(expression, context), engine)
    if old_data is not _UNDEFINED:
        return datadiff.diff(old_data, new_data).deleted


@specs.method
@specs.inject('finalizer', yaqltypes.Delegate('#finalize'))
def is_undef(finalizer, receiver):
    return finalizer(receiver) is _UNDEFINED


def register(context):
    context.register_function(get_new, name='new')
    context.register_function(get_old, name='old')
    context.register_function(decreased_roles)
    context.register_function(changed)
    context.register_function(changed_all)
    context.register_function(changed_any)
    context.register_function(added)
    context.register_function(deleted)
    context.register_function(is_undef)
