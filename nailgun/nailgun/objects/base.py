# -*- coding: utf-8 -*-

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

import json

from nailgun.api.serializers.base import BasicSerializer
from nailgun.db import db
from nailgun.errors import errors

from nailgun.openstack.common.db import api as db_api


_BACKEND_MAPPING = {'sqlalchemy': 'nailgun.db.sqlalchemy.api'}

IMPL = db_api.DBAPI(backend_mapping=_BACKEND_MAPPING)


class NailgunObject(object):

    serializer = BasicSerializer
    model = None
    schema = {
        "properties": {}
    }

    @classmethod
    def _check_field(cls, field):
        if field not in cls.schema["properties"]:
            raise errors.InvalidField(
                u"Invalid field '{0}' for object '{1}'".format(
                    field,
                    cls.__name__
                )
            )

    @classmethod
    def get_by_uid(cls, uid):
        return db().query(cls.model).get(uid)

    @classmethod
    def create(cls, data):
        new_obj = cls.model()
        for key, value in data.iteritems():
            setattr(new_obj, key, value)
        db().add(new_obj)
        db().flush()
        return new_obj

    @classmethod
    def update(cls, instance, data):
        instance.update(data)
        db().add(instance)
        db().flush()
        return instance

    @classmethod
    def delete(cls, instance):
        db().delete(instance)
        db().flush()

    @classmethod
    def to_dict(cls, instance, fields=None):
        return cls.serializer.serialize(instance, fields=fields)

    @classmethod
    def to_json(cls, instance, fields=None):
        return json.dumps(
            cls.to_dict(instance, fields=fields)
        )


class NailgunCollection(object):

    single = NailgunObject

    @classmethod
    def all(cls, yield_per=100):
        return db().query(
            cls.single.model
        ).yield_per(yield_per)

    @classmethod
    def filter_by(cls, yield_per=100, **kwargs):
        for k in kwargs.iterkeys():
            if k not in cls.single.schema["properties"]:
                raise AttributeError(
                    u"'{0}' object has no parameter '{1}'".format(
                        cls.single.__name__,
                        k
                    )
                )

        return db().query(
            cls.single.model
        ).filter_by(
            **kwargs
        ).yield_per(yield_per)

    @classmethod
    def to_list(cls, fields=None, yield_per=100, query=None):
        use_query = query or cls.all(yield_per=yield_per)
        return map(
            lambda o: cls.single.to_dict(o, fields=fields),
            use_query
        )

    @classmethod
    def to_json(cls, fields=None, yield_per=100, query=None):
        return json.dumps(
            cls.to_list(
                fields=fields,
                yield_per=yield_per,
                query=query
            )
        )

    @classmethod
    def create(cls, data):
        return cls.single.create(data)
