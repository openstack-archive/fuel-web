# -*- coding: utf-8 -*-

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

"""
Base classes for objects and collections
"""

import collections
import functools
from itertools import ifilter
import operator

from oslo_serialization import jsonutils
import six

from sqlalchemy import and_, not_
from sqlalchemy.orm import joinedload
from sqlalchemy.orm import Query

from nailgun.objects.serializers.base import BasicSerializer

from nailgun.db import db
from nailgun import errors


class NailgunObject(object):
    """Base class for objects"""

    #: Serializer class for object
    serializer = BasicSerializer

    #: SQLAlchemy model for object
    model = None

    @classmethod
    def get_by_uid(cls, uid, fail_if_not_found=False, lock_for_update=False):
        """Get instance by it's uid (PK in case of SQLAlchemy)

        :param uid: uid of object
        :param fail_if_not_found: raise an exception if object is not found
        :param lock_for_update: lock returned object for update (DB mutex)
        :returns: instance of an object (model)
        """
        q = db().query(cls.model)
        if lock_for_update:
            # todo(ikutukov): replace to the with_for_update
            # http://docs.sqlalchemy.org/en/latest/orm/query.html#sqlalchemy.
            # orm.query.Query.with_for_update
            q = q.with_lockmode('update')
        res = q.get(uid)
        if not res and fail_if_not_found:
            raise errors.ObjectNotFound(
                "Object '{0}' with UID={1} is not found in DB".format(
                    cls.__name__,
                    uid
                )
            )
        return res

    @classmethod
    def create(cls, data):
        """Create object instance with specified parameters in DB

        :param data: dictionary of key-value pairs as object fields
        :returns: instance of an object (model)
        """
        new_obj = cls.model()
        for key, value in six.iteritems(data):
            setattr(new_obj, key, value)
        db().add(new_obj)
        db().flush()
        return new_obj

    @classmethod
    def update(cls, instance, data):
        """Update existing instance with specified parameters

        :param instance: object (model) instance
        :param data: dictionary of key-value pairs as object fields
        :returns: instance of an object (model)
        """
        instance.update(data)
        db().add(instance)
        db().flush()
        return instance

    @classmethod
    def delete(cls, instance):
        """Delete object (model) instance

        :param instance: object (model) instance
        :returns: None
        """
        db().delete(instance)
        db().flush()

    @classmethod
    def bulk_delete(cls, instance_ids):
        db().query(cls.model).filter(
            cls.model.id.in_(instance_ids)).delete(synchronize_session='fetch')

    @classmethod
    def save(cls, instance=None):
        """Save current changes for instance in DB.

        Current transaction will be commited
        (in case of SQLAlchemy).

        :param instance: object (model) instance
        :returns: None
        """
        if instance:
            db().add(instance)
        db().commit()

    @classmethod
    def to_dict(cls, instance, fields=None, serializer=None):
        """Serialize instance to Python dict

        :param instance: object (model) instance
        :param fields: exact fields to serialize
        :param serializer: the custom serializer
        :returns: serialized object (model) as dictionary
        """
        serializer = serializer or cls.serializer
        return serializer.serialize(instance, fields=fields)

    @classmethod
    def to_json(cls, instance, fields=None, serializer=None):
        """Serialize instance to JSON

        :param instance: object (model) instance
        :param fields: exact fields to serialize
        :param serializer: the custom serializer
        :returns: serialized object (model) as JSON string
        """
        return jsonutils.dumps(
            cls.to_dict(instance, fields=fields, serializer=serializer)
        )

    @classmethod
    def compare(cls, instance, other, order_by):
        for field in order_by:
            a = getattr(instance, field['name'])
            b = getattr(other, field['name'])
            if a < b:
                return field['lt']
            elif a > b:
                return field['gt']
        return 0


class NailgunCollection(object):
    """Base class for object collections"""

    #: Single object class
    single = NailgunObject

    @classmethod
    def content_range(cls, first, last, total, valid):
        """Structure to set Content-Range header

        Defines structure necessary to implement paged requests.
        "total" is needed to let client calculate how many pages are available.
        "valid" is used to indicate that the requested page is valid
        (contains data) or not (outside of data range).
        Used in NailgunCollection.scope()

        :param first: first element (row) returned
        :param last: last element (row) returned
        :param total: total number of elements/rows (before pagination)
        :param valid: whether the pagination is within data range or not
        :returns: ContentRange object (collections.namedtuple) with 4 fields
        """
        rng = collections.namedtuple('ContentRange',
                                     ['first', 'last', 'total', 'valid'])
        rng.first = first
        rng.last = last
        rng.total = total
        rng.valid = valid
        return rng

    @classmethod
    def _is_iterable(cls, obj):
        return isinstance(
            obj,
            collections.Iterable
        )

    @classmethod
    def _is_query(cls, obj):
        return isinstance(
            obj,
            Query
        )

    @classmethod
    def all(cls):
        """Get all instances of this object (model)

        :returns: iterable (SQLAlchemy query)
        """
        return db().query(cls.single.model)

    @classmethod
    def scope(cls, pagination=None, filter_by=None):
        """Return a query to collection's objects and ContentRange object

        Return a filtered and paged query, according to the provided pagination
        (see api.v1.handlers.base.Pagination)
        Also return ContentRange - object with index of first element, last
        element and total count of elements in query(after filtering), and
        a 'valid' parameter to indicate that the paging scope (limit + offset)
        is valid or not (resulted in no data while there was data to provide)

        :param pagination: Pagination object
        :param filter_by: dict to filter objects {field1: value1, ...}
        :returns: SQLAlchemy query and ContentRange object
        """
        query = cls.all()
        content_range = None
        if filter_by:
            query = query.filter_by(**filter_by)
        query_full = query
        if pagination:
            if pagination.limit > 0 or pagination.limit is None:
                if pagination.order_by:
                    query = cls.order_by(query, pagination.order_by)
                if pagination.offset:
                    query = query.offset(pagination.offset)
                if pagination.limit > 0:
                    query = query.limit(pagination.limit)
            else:
                # making an empty result
                query = query.filter(False)
            if pagination.offset or pagination.limit is not None:
                total = query_full.count()
                selected = query.count() if pagination.limit != 0 else 0
                # first element index=1
                first = pagination.offset + 1 if pagination.offset else 1
                if selected == 0 or pagination.limit == 0:
                    # no data, report first and last as 0
                    first = last = 0
                elif pagination.limit > 0:
                        last = min(first + pagination.limit - 1, total)
                else:
                    last = total
                valid = selected > 0 or pagination.limit == 0 or total == 0
                content_range = cls.content_range(first, last, total, valid)
        return query, content_range

    @classmethod
    def _query_order_by(cls, query, order_by):
        """Adds order by clause into SQLAlchemy query

        :param query: SQLAlchemy query
        :param order_by: tuple of model fields names for ORDER BY criterion
        to SQLAlchemy query. If name starts with '-' desc ordering applies,
        else asc.
        """
        order_args = []
        for field_name in order_by:
            if field_name.startswith('-'):
                field_name = field_name.lstrip('-')
                ordering = 'desc'
            else:
                ordering = 'asc'
            field = getattr(cls.single.model, field_name)
            o_func = getattr(field, ordering)
            order_args.append(o_func())
        query = query.order_by(*order_args)
        return query

    @classmethod
    def _iterable_order_by(cls, iterable, order_by):
        """Sort iterable by field names in order_by

        :param iterable: model objects collection
        :param order_by: tuple of model fields names for sorting.
        If name starts with '-' desc ordering applies, else asc.
        """
        order_by_fields = []
        for field_name in order_by:
            if field_name.startswith('-'):
                order_by_fields.append({'name': field_name.lstrip('-'),
                                        'lt': 1, 'gt': -1})
            else:
                order_by_fields.append({'name': field_name,
                                        'lt': -1, 'gt': 1})
        # 'cmp' argument for 'sorted' function is removed in python3.
        # Next code should work fine for both python2 and python3
        key = functools.cmp_to_key(functools.partial(cls.single.compare,
                                                     order_by=order_by_fields))
        return sorted(iterable, key=key)

    @classmethod
    def get_iterable(cls, iterable, require=True):
        """Return either iterable or cls.all() when possible

        :param iterable: model objects collection
        :returns: original iterable or an SQLAlchemy query
        """
        if iterable is not None:
            if cls._is_iterable(iterable) or cls._is_query(iterable):
                return iterable
            else:
                raise TypeError("'%s' object is not iterable" % type(iterable))
        elif cls.single.model:
            return cls.all()
        elif require:
            raise ValueError('iterable not provided and single.model not set')

    @classmethod
    def order_by(cls, iterable, order_by):
        """Order given iterable by specified order_by.

        :param iterable: model objects collection
        :param order_by: tuple of model fields names or single field name for
            ORDER BY criterion to SQLAlchemy query. If name starts with '-'
            desc ordering applies, else asc.
        :type order_by: tuple of strings or string
        :returns: ordered iterable (SQLAlchemy query)
        """
        if not iterable or not order_by:
            return iterable
        use_iterable = cls.get_iterable(iterable)
        if not isinstance(order_by, (list, tuple)):
            order_by = (order_by,)
        if cls._is_query(use_iterable):
            return cls._query_order_by(use_iterable, order_by)
        elif cls._is_iterable(use_iterable):
            return cls._iterable_order_by(use_iterable, order_by)

    @classmethod
    def filter_by(cls, iterable, **kwargs):
        """Filter given iterable by specified kwargs.

        In case if iterable=None filters all object instances

        :param iterable: iterable (SQLAlchemy query)
        :param order_by: tuple of model fields names for ORDER BY criterion
            to SQLAlchemy query. If name starts with '-' desc ordering applies,
            else asc.
        :returns: filtered iterable (SQLAlchemy query)
        """
        use_iterable = cls.get_iterable(iterable)
        if cls._is_query(use_iterable):
            return use_iterable.filter_by(**kwargs)
        elif cls._is_iterable(use_iterable):
            return ifilter(
                lambda i: all(
                    (getattr(i, k) == v for k, v in six.iteritems(kwargs))
                ),
                use_iterable
            )
        else:
            raise TypeError("First argument should be iterable")

    @classmethod
    def filter_by_not(cls, iterable, **kwargs):
        """Filter given iterable by specified kwargs with negation.

        In case if `iterable` is `None` filters all object instances.

        :param iterable: iterable (SQLAlchemy query)
        :returns: filtered iterable (SQLAlchemy query)
        """
        use_iterable = cls.get_iterable(iterable)
        if cls._is_query(use_iterable):
            conditions = []
            for key, value in six.iteritems(kwargs):
                conditions.append(
                    getattr(cls.single.model, key) == value
                )
            return use_iterable.filter(not_(and_(*conditions)))
        elif cls._is_iterable(use_iterable):
            return ifilter(
                lambda i: not all(
                    (getattr(i, k) == v for k, v in six.iteritems(kwargs))
                ),
                use_iterable
            )

    @classmethod
    def lock_for_update(cls, iterable):
        """Use SELECT FOR UPDATE on a given iterable (query).

        In case if iterable=None returns all object instances

        :param iterable: iterable (SQLAlchemy query)
        :returns: filtered iterable (SQLAlchemy query)
        """
        use_iterable = cls.get_iterable(iterable)
        if cls._is_query(use_iterable):
            return use_iterable.with_lockmode('update')
        elif cls._is_iterable(use_iterable):
            # we can't lock abstract iterable, so returning as is
            # for compatibility
            return use_iterable

    @classmethod
    def filter_by_list(cls, iterable, field_name, list_of_values,
                       order_by=()):
        """Filter given iterable by list of list_of_values.

        In case if iterable=None filters all object instances

        :param iterable: iterable (SQLAlchemy query)
        :param field_name: filtering field name
        :param list_of_values: list of values for objects filtration
        :returns: filtered iterable (SQLAlchemy query)
        """
        field_getter = operator.attrgetter(field_name)
        use_iterable = cls.get_iterable(iterable)
        if cls._is_query(use_iterable):
            result = use_iterable.filter(
                field_getter(cls.single.model).in_(list_of_values)
            )
            result = cls.order_by(result, order_by)
            return result
        elif cls._is_iterable(use_iterable):
            return ifilter(
                lambda i: field_getter(i) in list_of_values,
                use_iterable
            )

    @classmethod
    def filter_by_id_list(cls, iterable, uid_list):
        """Filter given iterable by list of uids.

        In case if iterable=None filters all object instances

        :param iterable: iterable (SQLAlchemy query)
        :param uid_list: list of uids for objects
        :returns: filtered iterable (SQLAlchemy query)
        """
        return cls.filter_by_list(
            iterable,
            'id',
            uid_list,
        )

    @classmethod
    def eager_base(cls, iterable, options):
        """Eager load linked object instances (SQLAlchemy FKs).

        In case if iterable=None applies to all object instances

        :param iterable: iterable (SQLAlchemy query)
        :param options: list of sqlalchemy eagerload types
        :returns: iterable (SQLAlchemy query)
        """
        use_iterable = cls.get_iterable(iterable)
        if options:
            return use_iterable.options(*options)
        return use_iterable

    @classmethod
    def eager(cls, iterable, fields):
        """Eager load linked object instances (SQLAlchemy FKs).

        By default joinedload will be applied to every field.
        If you want to use custom eagerload method - use eager_base
        In case if iterable=None applies to all object instances

        :param iterable: iterable (SQLAlchemy query)
        :param fields: list of links (model FKs) to eagerload
        :returns: iterable (SQLAlchemy query)
        """
        options = [joinedload(field) for field in fields]
        return cls.eager_base(iterable, options)

    @classmethod
    def count(cls, iterable=None):
        use_iterable = cls.get_iterable(iterable)
        if cls._is_query(use_iterable):
            return use_iterable.count()
        elif cls._is_iterable(use_iterable):
            return len(list(iterable))

    @classmethod
    def to_list(cls, iterable=None, fields=None, serializer=None):
        """Serialize iterable to list of dicts

        In case if iterable=None serializes all object instances

        :param iterable: iterable (SQLAlchemy query)
        :param fields: exact fields to serialize
        :param serializer: the custom serializer
        :returns: collection of objects as a list of dicts
        """
        use_iterable = cls.get_iterable(iterable)
        return [
            cls.single.to_dict(o, fields=fields, serializer=serializer)
            for o in use_iterable
        ]

    @classmethod
    def to_json(cls, iterable=None, fields=None):
        """Serialize iterable to JSON

        In case if iterable=None serializes all object instances

        :param iterable: iterable (SQLAlchemy query)
        :param fields: exact fields to serialize
        :returns: collection of objects as a JSON string
        """
        return jsonutils.dumps(
            cls.to_list(
                fields=fields,
                iterable=iterable
            )
        )

    @classmethod
    def create(cls, data):
        """Create object instance with specified parameters in DB

        :param data: dictionary of key-value pairs as object fields
        :returns: instance of an object (model)
        """
        return cls.single.create(data)

    @classmethod
    def options(cls, iterable, *args):
        """Apply the given list of mapper options.

        In case if iterable=None applies to all object instances

        :param iterable: iterable (SQLAlchemy query)
        :param options: list of sqlalchemy mapper options
        :returns: iterable (SQLAlchemy query)
        """
        use_iterable = cls.get_iterable(iterable)
        if args:
            return use_iterable.options(*args)
        return use_iterable
