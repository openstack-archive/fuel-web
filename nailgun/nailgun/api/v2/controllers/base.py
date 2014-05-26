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

import inspect
from string import Template

import pecan
import pecan.hooks
import pecan.rest

from webob import exc

from nailgun.api.v1.validators.base import BasicValidator

from nailgun.errors import errors
from nailgun.logger import logger

from nailgun import objects

from nailgun.objects.serializers.base import BasicSerializer


class BaseController(pecan.rest.RestController):

    validator = BasicValidator
    serializer = BasicSerializer
    single = None
    collection = None
    eager = ()

    fields = []

    @classmethod
    def render(cls, instance, fields=None):
        return cls.serializer.serialize(
            instance,
            fields=fields or cls.fields
        )

    def http(cls, status_code, detail='', headers=None, **kwargs):
        """Return HTTP exception with status code specified. Useful
        for returning status codes like 401 Unauthorized or 403 Forbidden.

        :param status_code: the HTTP status code as an integer
        :param detail: the message to send along, as a string
        :param headers: the headeers to send along, as a dictionary
        """
        webob_exc = exc.status_map[status_code](
            detail=detail,
            headers=headers,
            **kwargs
        )
        webob_exc.plain_template_obj = Template(u'${body}')
        webob_exc.html_template_obj = Template(u'${body}')
        webob_exc.body_template_obj = Template(u'${detail}')
        return webob_exc

    def checked_data(self, validate_method=None, **kwargs):
        request = pecan.request
        try:
            data = kwargs.pop('data', request.body)
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

    def get_object_or_404(self, obj, *args, **kwargs):
        # should be in ('warning', 'Log message') format
        # (loglevel, message)
        log_404 = kwargs.pop("log_404") if "log_404" in kwargs else None
        log_get = kwargs.pop("log_get") if "log_get" in kwargs else None
        if "id" in kwargs:
            exist = obj.get_by_uid(kwargs["id"])
        elif len(args) > 0:
            exist = obj.get_by_uid(args[0])
        if not exist:
            if log_404:
                getattr(logger, log_404[0])(log_404[1])
            raise self.http(404, u'{0} not found'.format(obj.__name__))
        else:
            if log_get:
                getattr(logger, log_get[0])(log_get[1])
        return exist

    def get_objects_list_or_404(self, obj, ids):
        """Get list of objects

        :param model: model object
        :param ids: list of ids

        :http: 404 when not found
        :returns: query object
        """
        node_query = obj.collection.get_by_id_list(None, ids)
        objects_count = obj.collection.count(node_query)

        if len(set(ids)) != objects_count:
            raise self.http(
                404,
                '{0} not found'.format(obj.__name__)
            )

        return node_query

    @pecan.expose(template='json:', content_type='application/json')
    def get_one(self, obj_id):
        """:returns: JSONized REST object.
        :http: * 200 (OK)
               * 404 (object not found in db)
        """
        obj = self.get_object_or_404(
            self.single,
            obj_id
        )
        return self.single.to_dict(obj)

    @pecan.expose(template='json:', content_type='application/json')
    def get_all(self):
        """:returns: Collection of JSONized REST objects.
        :http: * 200 (OK)
        """
        q = self.collection.eager(self.eager, None)
        return self.collection.to_list(q)

    @pecan.expose(template='json:', content_type='application/json')
    def post_all(self):
        """:returns: JSONized REST object.
        :http: * 201 (object successfully created)
               * 400 (invalid object data specified)
               * 409 (object with such parameters already exists)
        """

        data = self.checked_data()

        response = pecan.response

        try:
            new_obj = self.collection.create(data)
        except errors.CannotCreate as exc:
            raise self.http(400, exc.message)

        response.status_int = 201
        return self.collection.single.to_dict(new_obj)

    @pecan.expose(template='json:', content_type='application/json')
    def delete_one(self, obj_id):
        """:returns: Empty string
        :http: * 204 (object successfully deleted)
               * 404 (object not found in db)
        """
        obj = self.get_object_or_404(
            self.single,
            obj_id
        )

        try:
            self.validator.validate_delete(obj)
        except errors.CannotDelete as exc:
            raise self.http(400, exc.message)

        self.single.delete(obj)
        raise self.http(204)

    @pecan.expose(template='json:', content_type='application/json')
    def put_one(self, obj_id):
        """:returns: JSONized REST object.
        :http: * 200 (OK)
               * 404 (object not found in db)
        """
        obj = self.get_object_or_404(
            self.single,
            obj_id
        )

        data = self.checked_data(
            self.validator.validate_update,
            instance=obj
        )

        self.single.update(obj, data)
        return self.single.to_dict(obj)

    def _handle_get(self, method, remainder):
        # route to a post_all or get if no additional parts are available
        if not remainder or remainder == ['']:
            controller = self._find_controller('get_all', 'get')
            if controller:
                return controller, []
            pecan.abort(405)

        controller = getattr(self, remainder[0], None)
        if controller and not inspect.ismethod(controller):
            handler, rem = pecan.routing.lookup_controller(
                controller,
                remainder[1:]
            )
            #if not len(instpect.getargspec(handler)["args"]) <= len(remainder)
            return (handler, rem)

        # finally, check for the regular get_one/get requests
        controller = self._find_controller('get_one', 'get')
        if controller:
            return controller, remainder

        pecan.abort(405)

    def _handle_post(self, method, remainder):
        # route to a post_all or get if no additional parts are available
        if not remainder or remainder == ['']:
            controller = self._find_controller('post_all', 'post')
            if controller:
                return controller, []
            pecan.abort(405)

        controller = getattr(self, remainder[0], None)
        if controller and not inspect.ismethod(controller):
            return pecan.routing.lookup_controller(controller, remainder[1:])

        # finally, check for the regular post_one/post requests
        controller = self._find_controller('post_one', 'post')
        if controller:
            return controller, remainder

        pecan.abort(405)

    def _handle_patch(self, method, remainder):
        # route to a patch_all or get if no additional parts are available
        if not remainder or remainder == ['']:
            controller = self._find_controller('patch_all', 'patch')
            if controller:
                return controller, []
            pecan.abort(405)

        controller = getattr(self, remainder[0], None)
        if controller and not inspect.ismethod(controller):
            return pecan.routing.lookup_controller(controller, remainder[1:])

        # finally, check for the regular patch_one/patch requests
        controller = self._find_controller('patch_one', 'patch')
        if controller:
            return controller, remainder

        pecan.abort(405)

    def _handle_put(self, method, remainder):
        # route to a put_all or get if no additional parts are available
        if not remainder or remainder == ['']:
            controller = self._find_controller('put_all', 'put')
            if controller:
                return controller, []
            pecan.abort(405)

        controller = getattr(self, remainder[0], None)
        if controller and not inspect.ismethod(controller):
            return pecan.routing.lookup_controller(controller, remainder[1:])

        # finally, check for the regular put_one/put requests
        controller = self._find_controller('put_one', 'put')
        if controller:
            return controller, remainder

        pecan.abort(405)

    def _handle_delete(self, method, remainder):
        # route to a delete_all or get if no additional parts are available
        if not remainder or remainder == ['']:
            controller = self._find_controller('delete_all', 'delete')
            if controller:
                return controller, []
            pecan.abort(405)

        controller = getattr(self, remainder[0], None)
        if controller and not inspect.ismethod(controller):
            return pecan.routing.lookup_controller(controller, remainder[1:])

        # finally, check for the regular delete_one/delete requests
        controller = self._find_controller('delete_one', 'delete')
        if controller:
            return controller, remainder

        pecan.abort(405)


class DeferredTaskController(BaseController):

    validator = BasicValidator
    single = objects.Task
    log_message = u"Starting deferred task on environment '{env_id}'"
    log_error = u"Error during execution of deferred task " \
                u"on environment '{env_id}': {error}"
    task_manager = None

    @pecan.expose(template='json:', content_type='application/json')
    def put_all(self, cluster_id):
        """:returns: JSONized Task object.
        :http: * 202 (task successfully executed)
               * 400 (invalid object data specified)
               * 404 (environment is not found)
               * 409 (task with such parameters already exists)
        """
        cluster = self.get_object_or_404(
            objects.Cluster,
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
            raise self.http(500, exc.message)

        raise self.http(202, self.single.to_json(task))
