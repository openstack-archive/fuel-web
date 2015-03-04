#    Copyright 2013 Mirantis, Inc.
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

import inspect


REVERSE_CACHE = {}


def _fill_cache(path, obj):
    from nailgun.api.v2.controllers.base import BaseController

    klass = obj
    if obj.__class__ != type:
        klass = obj.__class__

    for k, v in klass.__dict__.items():
        if isinstance(v, BaseController):
            klass_name = v.__class__.__name__
            new_path = '{0}/{1}'.format(path, k)

            if klass_name not in REVERSE_CACHE:
                REVERSE_CACHE[klass_name] = {
                    'class': v.__class__,
                    'parent': klass,
                    'parents': REVERSE_CACHE.get(
                        klass.__name__, {}).get('parents', []) + [klass],
                    'path': new_path,
                    'path_part': k,
                }

                # Some hacks for old handler names (this will allow no rewrite
                # on tests side)
                REVERSE_CACHE[klass_name.replace('Controller', 'Handler')] = \
                    REVERSE_CACHE[klass_name]
                collection_handler_name = klass_name.replace(
                    'Controller',
                    'CollectionHandler'
                )
                if collection_handler_name not in REVERSE_CACHE:
                    REVERSE_CACHE[collection_handler_name] = \
                        REVERSE_CACHE[klass_name]

                _fill_cache(new_path, v)


def construct_path_parts(klass_list, args):
    ret = []

    if len(klass_list) == 0:
        return []

    klass = klass_list[0]
    arg = None
    remaining_args = args
    if getattr(klass, 'single', None) and len(args) > 0:
        arg = args[0]
        # NOTE(pkaminski): This is a hack so that we allow not only
        # urls like /a/1/b/2 but also /a/b/1
        if arg is not None:
            if not isinstance(arg, basestring):
                arg = str(arg)
            remaining_args = args[1:]

    cache_elem = REVERSE_CACHE.get(klass.__name__)
    if cache_elem:
        ret.append(cache_elem['path_part'])
        if arg:
            ret.append(arg)

    return ret + construct_path_parts(klass_list[1:], remaining_args)


def reverse(class_name, kwargs=None, qs=None):
    """Returns url for given handler name.

    NOTE: in previous version we used kwargs. This has been deprecated in
    favor of args. The reason is generic functions: if we have 2 nested
    controllers:

    class A(BaseController):
        b = B

    and both of them have a generic get_one(self, obj_id) method, then we
    actually have no way to specify access to

    /a/1/b/2

    with a dict. This is because both arguments are named 'obj_id'.
    The only construct that can point us to that URL reliably is a tuple
    so you call reverse for the above case like

    reverse('B', (1, 2))

    Also, reversing for urls like

    /a/b/2

    is supported by calling

    reverse('B', (None, 2))

    :param class_name: Name of the controller class
    :param kwargs: dict with parameters passed to controller and its parents
    :param qa: dict with querystring parameters
    :return: URL
    """
    import urllib
    from nailgun.api.v2.controllers.root import RootController

    kwargs = kwargs or {}
    qs = qs or {}

    if not REVERSE_CACHE:
        _fill_cache('', RootController)

    controller = REVERSE_CACHE[class_name]
    klass = controller['class']

    #return '/{0}'.format(
    #    '/'.join(construct_path_parts(controller['parents'] + [klass],
    #                                  args)))

    # NOTE(pkaminski): The problem with Pecan's reverse is that a single
    # controller can serve both single and collection. This is a problem:
    # by doing reverse with just controller's class name we don't know
    # whether user wants to get all collection or a single object.
    # Solution is to either add 'type=single/collection' to the reverse
    # method or write Controllers the same way as was for old web.py
    # Handlers, i.e. CollectionHandler, SingleHandler as separate classes
    # This is an attempt to guess the path nicely
    args = []
    for type_ in ['all', 'one']:
        method_name = 'get_{0}'.format(type_)
        method = getattr(klass, method_name, None)
        if method:
            argspec = inspect.getargspec(method)
            if set(argspec.args[1:]) == set(kwargs):
                args = [kwargs[k] for k in argspec.args[1:]]
                break

    # HACK for generic obj_id
    if not args and len(kwargs) == 1:
        args = [kwargs.values()[0]]

    path = '/{0}'.format(
        '/'.join(construct_path_parts(controller['parents'] + [klass],
                                      args)))

    if qs:
        path = '{0}?{1}'.format(path, urllib.urlencode(qs))

    return path

    # Sometimes handlers have 'obj_id' instead of kwargs' 'cluster_id'
    # so we handle this case here gracefully
    #if len(kwargs) == 1 and isinstance(kwargs[kwargs.keys()[0]], int):
    #    kwargs['obj_id'] = kwargs[kwargs.keys()[0]]

    #params = ['%%(%s)s' % param for param in argspec.args[1:]]

    #url = '/'.join([path] + params)

    #return url % kwargs
