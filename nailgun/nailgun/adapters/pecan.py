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
import web
from webob import exc as webob_exc


def abort(status_code=None, message='', headers={}):
    """Raise an HTTP status code, as specified. Useful for returning status
    codes like 401 Unauthorized or 403 Forbidden.

    :param status_code: the HTTP status code as an integer
    :param message: the message to send along, as a string
    :param headers: the headeers to send along, as a dictionary
    """
    class _nocontent(web.HTTPError):
        message = 'No Content'

        def __init__(self, message=None):
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

    for key, value in headers:
        web.header(key, value, unique=True)

    raise exc


class _Request(object):
    """A proxy object that dispatch Pecan's API calls to web.py methods.
    Implements only those properties that are used in the project.
    """

    @property
    def GET(self):
        """Return a dict containing all the variables from the QUERY_STRING."""
        return dict(web.input(_method='GET'))

    @property
    def POST(self):
        """Return a dict containing all the variables from a form request.

        Form requests are typically POST requests, however PUT & PATCH requests
        with an appropriate Content-Type are also supported.
        """
        return dict(web.input(_method='POST'))

    @property
    def params(self):
        """A dict-like object containing both the parameters from the query
        string and request body.
        """
        return dict(web.input(_method='both'))

    @property
    def body(self):
        """Returns raw body data from the request."""
        return web.data()

    @property
    def path(self):
        """The path of the request, without host or query string."""
        return web.ctx.path

    @property
    def content_type(self):
        """Default value should be implemented with Hooks in Pecan."""
        return web.ctx.env.get("CONTENT_TYPE", "application/json")


request = _Request()


class _Response(object):
    """A proxy object that dispatch Pecan's API calls to web.py methods.
    Implements only those properties that are used in the project.
    """
    class _headers(object):
        def __getitem__(self, key):
            for header, value in web.ctx.headers:
                if header == key:
                    return value
            raise Exception('header does not exist')

        def __setitem__(self, key, value):
            web.header(key, value, unique=True)

        def __contains__(self, item):
            for header, value in web.ctx.headers:
                if header == item:
                    return True
            return False

    def __init__(self):
        self.headers = self._headers()

    @property
    def status(self):
        status = web.ctx.status
        return int(status.split(' ')[0])

    @status.setter
    def status(self, status):
        title = getattr(webob_exc.status_map[status], 'title')
        web.ctx.status = '{0} {1}'.format(status, title)

response = _Response()
