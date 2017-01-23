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
from oslo_serialization import jsonutils
import six
import traceback
import yaml

from distutils.version import StrictVersion
from sqlalchemy import exc as sa_exc
import web

from nailgun.api.v1.validators.base import BaseDefferedTaskValidator
from nailgun.api.v1.validators.base import BasicValidator
from nailgun.api.v1.validators.orchestrator_graph import \
    GraphSolverTasksValidator
from nailgun import consts
from nailgun.db import db
from nailgun import errors
from nailgun.logger import logger
from nailgun import objects
from nailgun.objects.serializers.base import BasicSerializer
from nailgun.orchestrator import orchestrator_graph
from nailgun.settings import settings
from nailgun import transactions
from nailgun import utils


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
    """Wrap all handlers calls so transaction is handled accordingly

    rollback if something wrong or commit changes otherwise. Please note,
    only HTTPError should be raised up from this function. All another
    possible errors should be handled.
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
    def http(cls, status_code, msg="", err_list=None, headers=None):
        """Raise an HTTP status code.

        Useful for returning status
        codes like 401 Unauthorized or 403 Forbidden.

        :param status_code: the HTTP status code as an integer
        :param msg: the message to send along, as a string
        :param err_list: list of fields with errors
        :param headers: the headers to send along, as a dictionary
        """
        class _nocontent(web.HTTPError):
            message = 'No Content'

            def __init__(self):
                super(_nocontent, self).__init__(
                    status='204 No Content',
                    data=self.message
                )

        class _range_not_satisfiable(web.HTTPError):
            message = 'Requested Range Not Satisfiable'

            def __init__(self):
                super(_range_not_satisfiable, self).__init__(
                    status='416 Range Not Satisfiable',
                    data=self.message
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
            410: web.gone,
            415: web.unsupportedmediatype,
            416: _range_not_satisfiable,

            500: web.internalerror,
        }

        # web.py has a poor exception design: some of them receive
        # the `message` argument and some of them not. the only
        # solution to set custom message is to assign message directly
        # to the `data` attribute. though, that won't work for
        # the `internalerror` because it tries to do magic with
        # application context without explicit `message` argument.
        try:
            exc = exc_status_map[status_code](message=msg)
        except TypeError:
            exc = exc_status_map[status_code]()
        exc.data = msg
        exc.err_list = err_list or []
        exc.status_code = status_code

        headers = headers or {}
        for key, value in headers.items():
            web.header(key, value)

        return exc

    @classmethod
    def checked_data(cls, validate_method=None, **kwargs):
        try:
            data = kwargs.pop('data', web.data())
            method = validate_method or cls.validator.validate
            valid_data = method(data, **kwargs)
        except (
            errors.InvalidInterfacesInfo,
            errors.InvalidMetadata
        ) as exc:
            objects.Notification.create({
                "topic": "error",
                "message": exc.message
            })
            raise cls.http(400, exc.message)
        except (
            errors.NotAllowed
        ) as exc:
            raise cls.http(403, exc.message)
        except (
            errors.AlreadyExists
        ) as exc:
            raise cls.http(409, exc.message)
        except (
            errors.InvalidData,
            errors.NodeOffline,
            errors.NoDeploymentTasks,
            errors.UnavailableRelease,
            errors.CannotCreate,
            errors.CannotUpdate,
            errors.CannotDelete,
            errors.CannotFindExtension,
        ) as exc:
            raise cls.http(400, exc.message)
        except (
            errors.ObjectNotFound,
        ) as exc:
            raise cls.http(404, exc.message)
        except Exception as exc:
            raise cls.http(500, traceback.format_exc())
        return valid_data

    def get_object_or_404(self, obj, *args, **kwargs):
        """Get object instance by ID

        :http: 404 when not found
        :returns: object instance
        """
        log_404 = kwargs.pop("log_404", None)
        log_get = kwargs.pop("log_get", None)
        uid = kwargs.get("id", (args[0] if args else None))
        if uid is None:
            if log_404:
                getattr(logger, log_404[0])(log_404[1])
            raise self.http(404, u'Invalid ID specified')
        else:
            instance = obj.get_by_uid(uid)
            if not instance:
                raise self.http(404, u'{0} not found'.format(obj.__name__))
            if log_get:
                getattr(logger, log_get[0])(log_get[1])
        return instance

    def get_objects_list_or_404(self, obj, ids):
        """Get list of objects

        :param obj: model object
        :param ids: list of ids

        :http: 404 when not found
        :returns: list of object instances
        """

        node_query = obj.filter_by_id_list(None, ids)
        objects_count = obj.count(node_query)
        if len(set(ids)) != objects_count:
            raise self.http(404, '{0} not found'.format(obj.__name__))

        return list(node_query)

    def raise_task(self, task):
        if task.status in [consts.TASK_STATUSES.ready,
                           consts.TASK_STATUSES.error]:
            status = 200
        else:
            status = 202

        raise self.http(status, objects.Task.to_json(task))

    @staticmethod
    def get_param_as_set(param_name, delimiter=',', default=None):
        """Parse array param from web.input()

        :param param_name: parameter name in web.input()
        :type param_name: str
        :param delimiter: delimiter
        :type delimiter: str
        :returns: list of items
        :rtype: set of str or None
        """
        if param_name in web.input():
            param = getattr(web.input(), param_name)
            if param == '':
                return set()
            else:
                return set(six.moves.map(
                    six.text_type.strip,
                    param.split(delimiter))
                )
        else:
            return default

    @staticmethod
    def get_requested_mime():
        accept = web.ctx.env.get("HTTP_ACCEPT", "application/json")
        accept = accept.strip().split(',')[0]
        accept = accept.split(';')[0]
        return accept


def json_resp(data):
    if isinstance(data, (dict, list)) or data is None:
        return jsonutils.dumps(data)
    else:
        return data


@decorator
def handle_errors(func, cls, *args, **kwargs):
    try:
        return func(cls, *args, **kwargs)
    except web.HTTPError as http_error:
        if http_error.status_code != 204:
            web.header('Content-Type', 'application/json', unique=True)
        if http_error.status_code >= 400:
            http_error.data = json_resp({
                "message": http_error.data,
                "errors": http_error.err_list
            })
        else:
            http_error.data = json_resp(http_error.data)
        raise
    except errors.NailgunException as exc:
        logger.exception('NailgunException occured')
        http_error = BaseHandler.http(400, exc.message)
        web.header('Content-Type', 'text/plain')
        raise http_error
    # intercepting all errors to avoid huge HTML output
    except Exception as exc:
        logger.exception('Unexpected exception occured')
        http_error = BaseHandler.http(
            500,
            (
                traceback.format_exc(exc)
                if settings.DEVELOPMENT
                else 'Unexpected exception, please check logs'
            )
        )
        http_error.data = json_resp(http_error.data)
        web.header('Content-Type', 'text/plain')
        raise http_error


@decorator
def validate(func, cls, *args, **kwargs):
    request_validation_needed = True

    resource_type = "single"
    if issubclass(
        cls.__class__,
        CollectionHandler
    ) and not func.func_name == "POST":
        resource_type = "collection"

    if (
        func.func_name in ("GET", "DELETE") or
        getattr(cls.__class__, 'validator', None) is None or
        (resource_type == "single" and not cls.validator.single_schema) or
        (resource_type == "collection" and not cls.validator.collection_schema)
    ):
        request_validation_needed = False

    if request_validation_needed:
        BaseHandler.checked_data(
            cls.validator.validate_request,
            resource_type=resource_type
        )

    return func(cls, *args, **kwargs)


@decorator
def serialize(func, cls, *args, **kwargs):
    """Set context-type of response based on Accept header.

    This decorator checks Accept header received from client
    and returns corresponding wrapper (only JSON is currently
    supported). It can be used as is:

    @handle_errors
    @validate
    @serialize
    def GET(self):
        ...
    """
    accepted_types = (
        "application/json",
        "application/x-yaml",
        "*/*"
    )
    accept = cls.get_requested_mime()
    if accept not in accepted_types:
        raise BaseHandler.http(415)

    resp = func(cls, *args, **kwargs)
    if accept == 'application/x-yaml':
        web.header('Content-Type', 'application/x-yaml', unique=True)
        return yaml.dump(resp, default_flow_style=False)
    else:
        # default is json
        web.header('Content-Type', 'application/json', unique=True)
        return jsonutils.dumps(resp)


class SingleHandler(BaseHandler):

    single = None
    validator = BasicValidator

    @handle_errors
    @serialize
    def GET(self, obj_id):
        """:returns: JSONized REST object.

        :http: * 200 (OK)
               * 404 (object not found in db)
        """
        obj = self.get_object_or_404(self.single, obj_id)
        return self.single.to_dict(obj)

    @handle_errors
    @validate
    @serialize
    def PUT(self, obj_id):
        """:returns: JSONized REST object.

        :http: * 200 (OK)
               * 404 (object not found in db)
        """
        obj = self.get_object_or_404(self.single, obj_id)

        data = self.checked_data(
            self.validator.validate_update,
            instance=obj
        )
        self.single.update(obj, data)
        return self.single.to_dict(obj)

    @handle_errors
    @validate
    def DELETE(self, obj_id):
        """:returns: Empty string

        :http: * 204 (object successfully deleted)
               * 404 (object not found in db)
        """
        obj = self.get_object_or_404(
            self.single,
            obj_id
        )

        self.checked_data(
            self.validator.validate_delete,
            instance=obj
        )

        self.single.delete(obj)
        raise self.http(204)


class Pagination(object):
    """Get pagination scope from init or HTTP request arguments"""

    def convert(self, x):
        """ret. None if x=None, else ret. x as int>=0; else raise 400"""

        val = x
        if val is not None:
            if type(val) is not int:
                try:
                    val = int(x)
                except ValueError:
                    raise BaseHandler.http(400, 'Cannot convert "%s" to int'
                                           % x)
            # raise on negative values
            if val < 0:
                raise BaseHandler.http(400, 'Negative limit/offset not \
                                       allowed')
            return val

    def get_order_by(self, order_by):
        if order_by:
            order_by = [s.strip() for s in order_by.split(',') if s.strip()]
        return order_by if order_by else None

    def __init__(self, limit=None, offset=None, order_by=None):
        if limit is not None or offset is not None or order_by is not None:
            # init with provided arguments
            self.limit = self.convert(limit)
            self.offset = self.convert(offset)
            self.order_by = self.get_order_by(order_by)
        else:
            # init with HTTP arguments
            self.limit = self.convert(web.input(limit=None).limit)
            self.offset = self.convert(web.input(offset=None).offset)
            self.order_by = self.get_order_by(web.input(order_by=None)
                                              .order_by)


class CollectionHandler(BaseHandler):

    collection = None
    validator = BasicValidator
    eager = ()

    def get_scoped_query_and_range(self, pagination=None, filter_by=None):
        """Get filtered+paged collection query and collection.ContentRange obj

        Return a scoped query, and if pagination is requested then also return
        ContentRange object (see NailgunCollection.content_range) to allow to
        set Content-Range header (outside of this functon).
        If pagination is not set/requested, return query to all collection's
        objects.
        Allows getting object count without getting objects - via
        content_range if pagination.limit=0.

        :param pagination: Pagination object
        :param filter_by: filter dict passed to query.filter_by(\*\*dict)
        :type filter_by: dict
        :returns: SQLAlchemy query and ContentRange object
        """
        pagination = pagination or Pagination()
        query = None
        content_range = None
        if self.collection and self.collection.single.model:
            query, content_range = self.collection.scope(pagination, filter_by)
            if content_range:
                if not content_range.valid:
                    raise self.http(416, 'Requested range "%s" cannot be '
                                    'satisfied' % content_range)
        return query, content_range

    def set_content_range(self, content_range):
        """Set Content-Range header to indicate partial data

        :param content_range: NailgunCollection.content_range named tuple
        """
        txt = 'objects {x.first}-{x.last}/{x.total}'.format(x=content_range)
        web.header('Content-Range', txt)

    @handle_errors
    @validate
    @serialize
    def GET(self):
        """:returns: Collection of JSONized REST objects.

        :http: * 200 (OK)
               * 400 (Bad Request)
               * 406 (requested range not satisfiable)
        """
        query, content_range = self.get_scoped_query_and_range()
        if content_range:
            self.set_content_range(content_range)
        q = self.collection.eager(query, self.eager)
        return self.collection.to_list(q)

    @handle_errors
    @validate
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


class DBSingletonHandler(BaseHandler):
    """Manages an object that is supposed to have only one entry in the DB"""

    single = None
    validator = BasicValidator
    not_found_error = "Object not found in the DB"

    def get_one_or_404(self):
        try:
            instance = self.single.get_one(fail_if_not_found=True)
        except errors.ObjectNotFound:
            raise self.http(404, self.not_found_error)

        return instance

    @handle_errors
    @validate
    @serialize
    def GET(self):
        """Get singleton object from DB

        :http: * 200 (OK)
               * 404 (Object not found in DB)
        """
        instance = self.get_one_or_404()

        return self.single.to_dict(instance)

    @handle_errors
    @validate
    @serialize
    def PUT(self):
        """Change object in DB

        :http: * 200 (OK)
               * 400 (Invalid data)
               * 404 (Object not present in DB)
        """
        data = self.checked_data(self.validator.validate_update)

        instance = self.get_one_or_404()

        self.single.update(instance, data)

        return self.single.to_dict(instance)

    @handle_errors
    @validate
    @serialize
    def PATCH(self):
        """Update object

        :http: * 200 (OK)
               * 400 (Invalid data)
               * 404 (Object not present in DB)
        """
        data = self.checked_data(self.validator.validate_update)

        instance = self.get_one_or_404()

        instance.update(utils.dict_merge(
            self.single.serializer.serialize(instance), data
        ))

        return self.single.to_dict(instance)


class OrchestratorDeploymentTasksHandler(SingleHandler):
    """Handler for deployment graph serialization."""

    validator = GraphSolverTasksValidator

    @handle_errors
    @validate
    @serialize
    def GET(self, obj_id):
        """:returns: Deployment tasks

        :http: * 200 OK
               * 404 (object not found)
        """
        obj = self.get_object_or_404(self.single, obj_id)
        end = web.input(end=None).end
        start = web.input(start=None).start
        graph_type = web.input(graph_type=None).graph_type or None
        # web.py depends on [] to understand that there will be multiple inputs
        include = web.input(include=[]).include

        # merged (cluster + plugins + release) tasks is returned for cluster
        # but the own release tasks is returned for release
        tasks = self.single.get_deployment_tasks(obj, graph_type=graph_type)

        if end or start:
            graph = orchestrator_graph.GraphSolver(tasks)

            for t in tasks:
                if StrictVersion(t.get('version')) >= \
                        StrictVersion(consts.TASK_CROSS_DEPENDENCY):
                    raise self.http(400, (
                        'Both "start" and "end" parameters are not allowed '
                        'for task-based deployment.'))

            try:
                return graph.filter_subgraph(
                    end=end, start=start, include=include).node.values()
            except errors.TaskNotFound as e:
                raise self.http(400, 'Cannot find task {0} by its '
                                     'name.'.format(e.task_name))
        return tasks

    @handle_errors
    @validate
    @serialize
    def PUT(self, obj_id):
        """:returns:  Deployment tasks

        :http: * 200 (OK)
               * 400 (invalid data specified)
               * 404 (object not found in db)
        """
        obj = self.get_object_or_404(self.single, obj_id)
        graph_type = web.input(graph_type=None).graph_type or None
        data = self.checked_data(
            self.validator.validate_update,
            instance=obj
        )
        deployment_graph = objects.DeploymentGraph.get_for_model(
            obj, graph_type=graph_type)
        if deployment_graph:
            objects.DeploymentGraph.update(
                deployment_graph, {'tasks': data})
        else:
            deployment_graph = objects.DeploymentGraph.create_for_model(
                {'tasks': data}, obj, graph_type=graph_type)
        return objects.DeploymentGraph.get_tasks(deployment_graph)

    def POST(self, obj_id):
        """Creation of metadata disallowed

        :http: * 405 (method not supported)
        """
        raise self.http(405, 'Create not supported for this entity')

    def DELETE(self, obj_id):
        """Deletion of metadata disallowed

        :http: * 405 (method not supported)
        """
        raise self.http(405, 'Delete not supported for this entity')


class TransactionExecutorHandler(BaseHandler):
    def start_transaction(self, cluster, options):
        """Starts new transaction.

        :param cluster: the cluster object
        :param options: the transaction parameters
        :return: JSONized task object
        """
        try:
            manager = transactions.TransactionsManager(cluster.id)
            self.raise_task(manager.execute(**options))
        except errors.ObjectNotFound as e:
            raise self.http(404, e.message)
        except errors.DeploymentAlreadyStarted as e:
            raise self.http(409, e.message)
        except errors.InvalidData as e:
            raise self.http(400, e.message)


# TODO(enchantner): rewrite more handlers to inherit from this
# and move more common code here, this is deprecated handler
class DeferredTaskHandler(TransactionExecutorHandler):
    """Abstract Deferred Task Handler"""

    validator = BaseDefferedTaskValidator
    single = objects.Task
    log_message = u"Starting deferred task on environment '{env_id}'"
    log_error = u"Error during execution of deferred task " \
                u"on environment '{env_id}': {error}"
    task_manager = None

    @classmethod
    def get_options(cls):
        return {}

    @classmethod
    def get_transaction_options(cls, cluster, options):
        """Finds graph for this action."""
        return None

    @handle_errors
    @validate
    def PUT(self, cluster_id):
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
            options = self.get_options()
        except ValueError as e:
            raise self.http(400, six.text_type(e))

        try:
            self.validator.validate(cluster)
        except errors.NailgunException as e:
            raise self.http(400, e.message)

        if objects.Release.is_lcm_supported(cluster.release):
            # try to get new graph to run transaction manager
            try:
                transaction_options = self.get_transaction_options(
                    cluster, options
                )
            except errors.NailgunException as e:
                logger.exception("Failed to get transaction options")
                raise self.http(400, msg=six.text_type(e))

            if transaction_options:
                return self.start_transaction(cluster, transaction_options)

        try:

            task_manager = self.task_manager(cluster_id=cluster.id)
            task = task_manager.execute(**options)
        except (
            errors.AlreadyExists,
            errors.StopAlreadyRunning
        ) as exc:
            raise self.http(409, exc.message)
        except (
            errors.DeploymentNotRunning,
            errors.NoDeploymentTasks,
            errors.WrongNodeStatus,
            errors.UnavailableRelease,
            errors.CannotBeStopped,
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
        self.raise_task(task)
