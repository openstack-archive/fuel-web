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

from datetime import datetime
import itertools
import jinja2
import os.path
import Queue
import StringIO
import sys
import yaml

from sqlalchemy import orm
import sqlalchemy.types

from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun.logger import logger
from nailgun import objects
from nailgun.openstack.common import jsonutils
from nailgun.settings import settings
from nailgun.utils import dict_merge


def capitalize_model_name(model_name):
    return ''.join(map(lambda s: s.capitalize(), model_name.split('_')))


def template_fixture(fileobj, **kwargs):
    if not kwargs.get('settings'):
        kwargs["settings"] = settings
    t = jinja2.Template(fileobj.read())
    return StringIO.StringIO(t.render(**kwargs))


def load_fixture(fileobj, loader=None):
    if not loader:
        loaders = {'.json': jsonutils, '.yaml': yaml, '.yml': yaml}
        extension = os.path.splitext(fileobj.name)[1]
        if extension not in loaders:
            raise Exception("Unknown file extension '{0}'".format(extension))
        loader = loaders[extension]
    fixture = loader.load(
        template_fixture(fileobj)
    )
    fixture = filter(lambda obj: obj.get('pk') is not None, fixture)
    for i in range(0, len(fixture)):
        def extend(obj):
            if 'extend' in obj:
                obj['extend'] = extend(obj['extend'])
            return dict_merge(obj.get('extend', {}), obj)
        fixture[i] = extend(fixture[i])
        fixture[i].pop('extend', None)

    return fixture


def upload_fixture(fileobj, loader=None):
    fixture = load_fixture(fileobj, loader)

    queue = Queue.Queue()
    keys = {}

    for obj in fixture:
        pk = obj['pk']
        model_name = obj["model"].split(".")[1]

        try:
            itertools.dropwhile(
                lambda m: not hasattr(models, m),
                [model_name.capitalize(),
                 "".join(map(lambda n: n.capitalize(), model_name.split("_")))]
            ).next()
        except StopIteration:
            raise Exception("Couldn't find model {0}".format(model_name))

        obj['model'] = getattr(models, capitalize_model_name(model_name))
        keys[obj['model'].__tablename__] = {}

        # Check if it's already uploaded
        obj_from_db = db().query(obj['model']).get(pk)
        if obj_from_db:
            logger.info("Fixture model '%s' with pk='%s' already"
                        " uploaded. Skipping", model_name, pk)
            continue
        queue.put(obj)

    pending_objects = []

    while True:
        try:
            obj = queue.get_nowait()
        except Exception:
            break

        # NOTE(ikalnitsly):
        #   In order to add a release to Nailgun we have to fill two tables:
        #   releases and release_orchestrator_data. By using former fixture
        #   approach we can't do it, since the fixture is bond to only one
        #   database model and can't deal with additional logic. Therefore
        #   we need to use Nailgun's objects which know how to handle it.
        #
        # TODO(ikalnitsky):
        #   Rewrite fixture logic - it must be simple and obvious.
        if obj['model'] is objects.Release.model:
            objects.Release.create(obj['fields'])
            continue

        new_obj = obj['model']()
        fk_fields = {}
        for field, value in obj["fields"].iteritems():
            f = getattr(obj['model'], field)
            impl = getattr(f, 'impl', None)
            fk_model = None
            try:
                if hasattr(f.comparator.prop, "argument"):
                    if hasattr(f.comparator.prop.argument, "__call__"):
                        fk_model = f.comparator.prop.argument()
                    else:
                        fk_model = f.comparator.prop.argument.class_
            except AttributeError:
                pass

            if fk_model:
                if value not in keys[fk_model.__tablename__]:
                    if obj not in pending_objects:
                        queue.put(obj)
                        pending_objects.append(obj)
                        continue
                    else:
                        logger.error(
                            u"Can't resolve foreign key "
                            "'{0}' for object '{1}'".format(
                                field,
                                obj["model"]
                            )
                        )
                        break
                else:
                    value = keys[fk_model.__tablename__][value].id

            if isinstance(impl, orm.attributes.ScalarObjectAttributeImpl):
                if value:
                    fk_fields[field] = (value, fk_model)
            elif isinstance(impl, orm.attributes.CollectionAttributeImpl):
                if value:
                    fk_fields[field] = (value, fk_model)
            elif hasattr(f, 'property') and isinstance(
                f.property.columns[0].type, sqlalchemy.types.DateTime
            ):
                if value:
                    setattr(
                        new_obj,
                        field,
                        datetime.strptime(value, "%d-%m-%Y %H:%M:%S")
                    )
                else:
                    setattr(
                        new_obj,
                        field,
                        datetime.now()
                    )
            else:
                setattr(new_obj, field, value)

        for field, data in fk_fields.iteritems():
            if isinstance(data[0], int):
                setattr(new_obj, field, db().query(data[1]).get(data[0]))
            elif isinstance(data[0], list):
                for v in data[0]:
                    getattr(new_obj, field).append(
                        db().query(data[1]).get(v)
                    )
        db().add(new_obj)
        db().commit()
        keys[obj['model'].__tablename__][obj["pk"]] = new_obj

        # UGLY HACK for testing
        if new_obj.__class__.__name__ == 'Node':
            objects.Node.create_attributes(new_obj)
            objects.Node.update_volumes(new_obj)
            objects.Node.update_interfaces(new_obj)
            db().commit()


def upload_fixtures():
    fixtures_paths = [
        '/etc/nailgun/fixtures',
        os.path.join(os.path.dirname(__file__), '..', '..', 'fixtures')
    ]
    for orig_path in settings.FIXTURES_TO_UPLOAD:
        if os.path.isabs(orig_path):
            path = orig_path
        else:
            for fixtures_path in fixtures_paths:
                path = os.path.abspath(
                    os.path.join(
                        fixtures_path,
                        orig_path
                    )
                )
                if os.access(path, os.R_OK):
                    break
        if os.access(path, os.R_OK):
            with open(path, "r") as fileobj:
                upload_fixture(fileobj)
            logger.info("Fixture has been uploaded from file: %s", path)


def dump_fixture(model_name):
    dump = []
    app_name = 'nailgun'
    model = getattr(models, capitalize_model_name(model_name))
    for obj in db().query(model).all():
        obj_dump = {}
        obj_dump['pk'] = getattr(obj, model.__mapper__.primary_key[0].name)
        obj_dump['model'] = "%s.%s" % (app_name, model_name)
        obj_dump['fields'] = {}
        dump.append(obj_dump)
        for prop in model.__mapper__.iterate_properties:
            if isinstance(prop, sqlalchemy.orm.ColumnProperty):
                field = str(prop.key)
                value = getattr(obj, field)
                if value is None:
                    continue
                if not isinstance(value, (
                        list, dict, str, unicode, int, float, bool)):
                    value = ""
                obj_dump['fields'][field] = value
    sys.stdout.write(jsonutils.dumps(dump, indent=4))
