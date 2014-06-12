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
from decorator import decorator
import json

from sqlalchemy import exc as sa_exc
import web

from nailgun.api.serializers.base import BasicSerializer
from nailgun.api.validators.base import BasicValidator
from nailgun.db import db

# TODO(enchantner): let's switch to Cluster object in the future
from nailgun.db.sqlalchemy.models import Cluster

from nailgun.errors import errors
from nailgun.logger import logger

from nailgun import objects


def check_client_content_type(handler):
    content_type = web.ctx.env.get("CONTENT_TYPE", "application/json")
    if web.ctx.path.startswith("/api")\
            and not content_type.startswith("application/json"):
        raise handler.http(415)
    return handler()


def forbid_client_caching(handler):
    if web.ctx.path.startswith("/api"):
        web.header('Cache-Control',
                   'store, no-cache, must-revalidate,'
                   ' post-check=0, pre-check=0')
        web.header('Pragma', 'no-cache')
        dt = datetime.fromtimestamp(0).strftime(
            '%a, %d %b %Y %H:%M:%S GMT'
        )
        web.header('Expires', dt)
    return handler()


def load_db_driver(handler):
    """Wrap all handlers calls in a special construction, that's call
    rollback if something wrong or commit changes otherwise. Please note,
    only HTTPError should be rised up from this function. All another
    possible errors should be handle.
    """
    try:
        # execute handler and commit changes if all is ok
        response = handler()
        db.commit()
        return response

    except web.HTTPError:
        # a special case: commit changes if http error ends with
        # 200, 201, 202, etc
        if web.ctx.status.startswith('2'):
            db.commit()
        else:
            db.rollback()
        raise

    except (sa_exc.IntegrityError, sa_exc.DataError) as exc:
        # respond a "400 Bad Request" if database constraints were broken
        db.rollback()
        raise BaseHandler.http(400, exc.message)

    except Exception:
        db.rollback()
        raise

    finally:
        db.remove()


@decorator
def content_json(func, *args, **kwargs):
    try:
        data = func(*args, **kwargs)
    except web.notmodified:
        raise
    except web.HTTPError as http_error:
        web.header('Content-Type', 'application/json')
        if isinstance(http_error.data, (dict, list)):
            http_error.data = build_json_response(http_error.data)
        raise
    web.header('Content-Type', 'application/json')
    return build_json_response(data)


def build_json_response(data):
    web.header('Content-Type', 'application/json')
    if type(data) in (dict, list):
        return json.dumps(data)
    return data


class BaseHandler(object):
    validator = BasicValidator
    serializer = BasicSerializer

    fields = []

    @classmethod
    def render(cls, instance, fields=None):
        return cls.serializer.serialize(
            instance,
            fields=fields or cls.fields
        )

    @classmethod
    def http(cls, status_code, message='', headers=None):
        """Raise an HTTP status code, as specified. Useful for returning status
        codes like 401 Unauthorized or 403 Forbidden.

        :param status_code: the HTTP status code as an integer
        :param message: the message to send along, as a string
        :param headers: the headeers to send along, as a dictionary
        """
        class _nocontent(web.HTTPError):
            message = 'No Content'

            def __init__(self, message=''):
                super(_nocontent, self).__init__(
                    status='204 No Content',
                    data=message or self.message
                )

        exc_status_map = {
            200: web.ok,
            201: web.created,
            202: web.accepted,
            204: _nocontent,

            301: web.redirect,
            302: web.found,

            400: web.badrequest,
            401: web.unauthorized,
            403: web.forbidden,
            404: web.notfound,
            405: web.nomethod,
            406: web.notacceptable,
            409: web.conflict,
            415: web.unsupportedmediatype,

            500: web.internalerror,
        }

        exc = exc_status_map[status_code]()
        exc.data = message

        headers = headers or {}
        for key, value in headers.items():
            web.header(key, value)

        return exc

    def checked_data(self, validate_method=None, **kwargs):
        try:
            data = kwargs.pop('data', web.data())
            method = validate_method or self.validator.validate

            valid_data = method(data, **kwargs)
        except (
            errors.InvalidInterfacesInfo,
            errors.InvalidMetadata
        ) as exc:
            objects.Notification.create({
                "topic": "error",
                "message": exc.message
            })
            raise self.http(400, exc.message)
        except (
            errors.NotAllowed,
        ) as exc:
            raise self.http(403, exc.message)
        except (
            errors.AlreadyExists
        ) as exc:
            raise self.http(409, exc.message)
        except (
            errors.InvalidData,
            errors.NodeOffline,
        ) as exc:
            raise self.http(400, exc.message)
        except Exception as exc:
            raise
        return valid_data

    def get_object_or_404(self, model, *args, **kwargs):
        # should be in ('warning', 'Log message') format
        # (loglevel, message)
        log_404 = kwargs.pop("log_404") if "log_404" in kwargs else None
        log_get = kwargs.pop("log_get") if "log_get" in kwargs else None
        if "id" in kwargs:
            obj = db().query(model).get(kwargs["id"])
        elif len(args) > 0:
            obj = db().query(model).get(args[0])
        else:
            obj = db().query(model).filter(**kwargs).all()
        if not obj:
            if log_404:
                getattr(logger, log_404[0])(log_404[1])
            raise self.http(404, '{0} not found'.format(model.__name__))
        else:
            if log_get:
                getattr(logger, log_get[0])(log_get[1])
        return obj

    def get_objects_list_or_404(self, model, ids):
        """Get list of objects

        :param model: model object
        :param ids: list of ids

        :http: 404 when not found
        :returns: query object
        """
        node_query = db.query(model).filter(model.id.in_(ids))
        objects_count = node_query.count()

        if len(set(ids)) != objects_count:
            raise self.http(404, '{0} not found'.format(model.__name__))

        return node_query


class SingleHandler(BaseHandler):

    validator = BasicValidator
    single = None

    @content_json
    def GET(self, obj_id):
        """:returns: JSONized REST object.
        :http: * 200 (OK)
               * 404 (object not found in db)
        """
        obj = self.get_object_or_404(
            self.single.model,
            obj_id
        )
        return self.single.to_json(obj)

    @content_json
    def PUT(self, obj_id):
        """:returns: JSONized REST object.
        :http: * 200 (OK)
               * 404 (object not found in db)
        """
        obj = self.get_object_or_404(
            self.single.model,
            obj_id
        )

        data = self.checked_data(
            self.validator.validate_update,
            instance=obj
        )

        self.single.update(obj, data)
        return self.single.to_json(obj)

    def DELETE(self, obj_id):
        """:returns: Empty string
        :http: * 204 (object successfully deleted)
               * 404 (object not found in db)
        """
        obj = self.get_object_or_404(
            self.single.model,
            obj_id
        )

        try:
            self.validator.validate_delete(obj)
        except errors.CannotDelete as exc:
            raise self.http(400, exc.message)

        self.single.delete(obj)
        raise self.http(204)


class CollectionHandler(BaseHandler):

    validator = BasicValidator
    collection = None
    eager = ()

    @content_json
    def GET(self):
        """:returns: Collection of JSONized REST objects.
        :http: * 200 (OK)
        """
        q = self.collection.eager(None, self.eager)
        return self.collection.to_json(q)

    @content_json
    def POST(self):
        """:returns: JSONized REST object.
        :http: * 201 (object successfully created)
               * 400 (invalid object data specified)
               * 409 (object with such parameters already exists)
        """

        data = self.checked_data()

        try:
            new_obj = self.collection.create(data)
        except errors.CannotCreate as exc:
            raise self.http(400, exc.message)

        raise self.http(201, self.collection.single.to_json(new_obj))


# TODO(enchantner): rewrite more handlers to inherit from this
# and move more common code here
class DeferredTaskHandler(BaseHandler):
    """Abstract Deferred Task Handler
    """

    validator = BasicValidator
    single = objects.Task
    log_message = u"Starting deferred task on environment '{env_id}'"
    log_error = u"Error during execution of deferred task " \
                u"on environment '{env_id}': {error}"
    task_manager = None

    @content_json
    def PUT(self, cluster_id):
        """:returns: JSONized Task object.
        :http: * 202 (task successfully executed)
               * 400 (invalid object data specified)
               * 404 (environment is not found)
               * 409 (task with such parameters already exists)
        """
        cluster = self.get_object_or_404(
            Cluster,
            cluster_id,
            log_404=(
                u"warning",
                u"Error: there is no cluster "
                u"with id '{0}' in DB.".format(cluster_id)
            )
        )

        logger.info(self.log_message.format(env_id=cluster_id))

        try:
            task_manager = self.task_manager(cluster_id=cluster.id)
            task = task_manager.execute()
        except (
            errors.AlreadyExists,
            errors.StopAlreadyRunning
        ) as exc:
            raise self.http(409, exc.message)
        except (
            errors.DeploymentNotRunning,
            errors.WrongNodeStatus
        ) as exc:
            raise self.http(400, exc.message)
        except Exception as exc:
            logger.error(
                self.log_error.format(
                    env_id=cluster_id,
                    error=str(exc)
                )
            )
            # let it be 500
            raise

        raise self.http(202, self.single.to_json(task))
