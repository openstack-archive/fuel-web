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

import re
import wsgiref

from nailgun import plugins

from nailgun.openstack.common import jsonutils


class HTTPPluginMiddleware(object):

    def __init__(self, app):
        self.app = app
        self.re_plugins = re.compile(
            r"https?://[^/]+/api/plugins/(?P<plugin_name>[^/]*)"
        )

    def __call__(self, environ, start_response):
        url = wsgiref.util.request_uri(environ)

        match = self.re_plugins.match(url)
        if match:
            plugin_name = match.groupdict()["plugin_name"]
            api_plugins = plugins.get_api_plugins()
            if plugin_name:
                if plugin_name in api_plugins:
                    app = api_plugins[plugin_name].application
                    if app:
                        for _ in xrange(3):
                            wsgiref.util.shift_path_info(environ)
                        return app()(environ, start_response)
                else:
                    start_response(
                        '404 Not Found',
                        [('Content-Type', 'application/json')]
                    )
                    return [jsonutils.dumps({
                        "error": u"Plugin {0} not found".format(plugin_name)
                    })]
            else:
                list_plugins = plugins.get_all_plugins().keys()
                start_response(
                    '200 OK',
                    [('Content-Type', 'application/json')]
                )
                return [jsonutils.dumps(list_plugins)]
        return self.app(environ, start_response)
