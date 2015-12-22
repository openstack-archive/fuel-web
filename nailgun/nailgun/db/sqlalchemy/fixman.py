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
import jinja2
import os.path
import Queue
from six import StringIO
import sys
import yaml

from oslo_serialization import jsonutils
from sqlalchemy import orm
import sqlalchemy.types

from nailgun.db import db
from nailgun.db.sqlalchemy import models
from nailgun.extensions import fire_callback_on_node_create
from nailgun.logger import logger
from nailgun import objects
from nailgun.settings import settings
from nailgun.utils import dict_merge


def capitalize_model_name(model_name):
    return ''.join(map(lambda s: s.capitalize(), model_name.split('_')))


def load_fake_deployment_tasks(apply_to_db=True, commit=True):
    """Load fake deployment tasks

    :param apply_to_db: if True applying to all releases in db
    :param commit: boolean
    """
    fxtr_path = os.path.join(get_base_fixtures_path(), 'deployment_tasks.yaml')
    with open(fxtr_path) as f:
        deployment_tasks = yaml.load(f)

    if apply_to_db:
        for rel in db().query(models.Release).all():
            rel.deployment_tasks = deployment_tasks
        if commit:
            db().commit()
    else:
        return deployment_tasks


def template_fixture(fileobj, **kwargs):
    if not kwargs.get('settings'):
        kwargs["settings"] = settings
    t = jinja2.Template(fileobj.read())
    return StringIO(t.render(**kwargs))


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

    def extend(obj):
        if 'extend' in obj:
            obj['extend'] = extend(obj['extend'])
        return dict_merge(obj.get('extend', {}), obj)

    for i, obj in enumerate(fixture):
        fixture[i] = extend(fixture[i])
        fixture[i].pop('extend', None)

    return fixture


def _get_related_model(db_field):
    """Returns related DB model if db_field is relationship property

    :param db_field: SQLAlchemy column
    :return: SQLAlchemy model or None
    """
    fk_model = None
    try:
        if hasattr(db_field.comparator.prop, "argument"):
            if hasattr(db_field.comparator.prop.argument, "__call__"):
                fk_model = db_field.comparator.prop.argument()
            else:
                fk_model = db_field.comparator.prop.argument.class_
    except AttributeError:
        pass
    return fk_model


def _get_name_and_db_model(fixture_data):
    """Extracts model_name and model class from fixture['model'] value

    :param fixture_data: fixture data
    :type fixture_data: dict
    :return: model_name and SQLAlchemy model class
    :rtype: tuple
    """
    model_name = fixture_data["model"].split(".")[1]
    return model_name, getattr(models, model_name)


def upload_fixture(fileobj, loader=None):
    fixture = load_fixture(fileobj, loader)

    # Filtering fixtures with save_to_db False and without identity_fields
    fixture = [obj for obj in fixture if obj.get('save_to_db', True)]

    queue = Queue.Queue()

    # Created objects cache
    created_objects = {}

    for obj in fixture:
        identity_fields = obj.get('identity_fields', [])
        model_name, model = _get_name_and_db_model(obj)

        if not identity_fields:
            logger.warning("No identity fields for '{0}' in fixture '{1}'. "
                           "Checking of presence in DB will be skipped.".
                           format(obj['model'],
                                  getattr(fileobj, 'name', None) or fileobj))

        if not hasattr(models, model_name):
            raise Exception("Couldn't find model {0}".format(model_name))

        created_objects[model_name] = {}

        # Check if fixture already uploaded
        obj_from_db = None
        query = db().query(model)
        identity_values = []
        for identity_field in identity_fields:
            column = getattr(model.__table__.columns, identity_field)
            value = obj['fields'][identity_field]
            identity_values.append(value)
            query = query.filter(column == value)
            obj_from_db = query.first()

        if obj_from_db:
            logger.info("Fixture '%s' from '%s' with %s=%s already"
                        " uploaded. Skipping.", model_name, fileobj.name,
                        identity_fields, identity_values)
            continue
        queue.put(obj)

        # Adding child fixtures
        for child in obj.get('children', []):
            child_model_name, child_model = _get_name_and_db_model(child)
            created_objects[child_model_name] = {}
            queue.put(child)

    while True:
        try:
            obj = queue.get_nowait()
        except Exception:
            break

        model_name, model = _get_name_and_db_model(obj)
        new_obj = model()

        fk_fields = {}
        for field, value in obj["fields"].iteritems():
            f = getattr(model, field)
            impl = getattr(f, 'impl', None)
            fk_model = _get_related_model(f)

            if fk_model:
                fk_model_name = fk_model.__name__
                last_id = max(created_objects[fk_model_name].keys())
                value = created_objects[fk_model_name][last_id].id

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
        db().flush()
        added_obj_pk = getattr(
            new_obj, model.__mapper__.primary_key[0].name)
        created_objects[model_name][added_obj_pk] = new_obj

        # UGLY HACK for testing
        if new_obj.__class__.__name__ == 'Node':
            objects.Node.create_attributes(new_obj)
            objects.Node.update_interfaces(new_obj)
            fire_callback_on_node_create(new_obj)
            db().flush()

    db().commit()


def get_base_fixtures_path():
    return os.path.join(os.path.dirname(__file__), '..', '..', 'fixtures')


def get_all_fixtures_paths():
    return [
        '/etc/nailgun/fixtures',
        get_base_fixtures_path(),
    ]


def upload_fixtures():
    fixtures_paths = get_all_fixtures_paths()
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
    model = getattr(models, model_name)
    for obj in db().query(model).all():
        obj_dump = {}
        parent_key_name = model.__mapper__.primary_key[0].name
        obj_dump['identity_fields'] = [parent_key_name]
        obj_dump['id'] = getattr(obj, parent_key_name)
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
