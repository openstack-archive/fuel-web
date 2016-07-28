# -*- coding: utf-8 -*-

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


from decorator import decorator
from oslo_serialization import jsonutils
import traceback
import web

from nailgun.errors.base import NailgunException
from nailgun.logger import logger
from nailgun.settings import settings


def json_resp(data):
    if isinstance(data, (dict, list)) or data is None:
        return jsonutils.dumps(data)
    else:
        return data


@decorator
def handle_errors(func, cls, *args, **kwargs):
    from nailgun.api.v1.handlers.base import BaseHandler
    try:
        return func(cls, *args, **kwargs)
    except web.notmodified:
        raise
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
    except NailgunException as exc:
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
    from nailgun.api.v1.handlers.base import BaseHandler
    from nailgun.api.v1.handlers.base import CollectionHandler
    request_validate_needed = True
    response_validate_needed = True

    resource_type = "single"
    if issubclass(
        cls.__class__,
        CollectionHandler
    ) and not func.func_name == "POST":
        resource_type = "collection"

    if (
        func.func_name in ("GET", "DELETE") or
        getattr(cls.__class__, 'validator', None) is None or
        resource_type == "single" and not cls.validator.single_schema or
        resource_type == "collection" and not cls.validator.collection_schema
    ):
        request_validate_needed = False

    if request_validate_needed:
        BaseHandler.checked_data(
            cls.validator.validate_request,
            resource_type=resource_type
        )

    resp = func(cls, *args, **kwargs)

    if all([
        settings.DEVELOPMENT,
        response_validate_needed,
        getattr(cls.__class__, 'validator', None) is not None
    ]):
        BaseHandler.checked_data(
            cls.validator.validate_response,
            resource_type=resource_type
        )

    return resp


@decorator
def to_json(func, cls, *args, **kwargs):
    """Set context-type of response based on Accept header

    This decorator checks Accept header received from client
    and returns corresponding wrapper (only JSON is currently
    supported). It can be used as is:

    @handle_errors
    @validate
    @to_json
    def GET(self):
        ...
    """
    from nailgun.api.v1.handlers.base import BaseHandler
    accepted_types = [
        "application/json",
        "*/*"
    ]
    accept = web.ctx.env.get("HTTP_ACCEPT", "application/json")
    if any(map(lambda m: m in accept, accepted_types)):
        resp = func(cls, *args, **kwargs)
        web.header('Content-Type', 'application/json', unique=True)
        if not isinstance(resp, (dict, list)) and resp is not None:
            raise BaseHandler.http(415, repr(resp))
        return jsonutils.dumps(resp)
    else:
        from nailgun.api.v1.handlers.base import BaseHandler
        raise BaseHandler.http(415)
