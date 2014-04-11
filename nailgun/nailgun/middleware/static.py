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

import os.path
import urllib

from web.httpserver import StaticApp

from nailgun.settings import settings


class NailgunStaticApp(StaticApp):

    def translate_path(self, path):
        root = settings.STATIC_DIR
        path = path.split('?', 1)[0].split('#', 1)[0]
        if path.startswith("/static/"):
            path = path[7:]
        path = os.path.normpath(urllib.unquote(path))
        words = path.split('/')
        words = filter(None, words)

        path = root
        for word in words:
            drive, word = os.path.splitdrive(word)
            head, word = os.path.split(word)
            if word in (os.curdir, os.pardir):
                continue
            path = os.path.join(path, word)

        return path


class StaticMiddleware(object):
    """WSGI middleware for serving static files."""
    def __init__(self, app, prefix='/static/'):
        self.app = app
        self.prefix = prefix

    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO', '')
        path = self.normpath(path)

        if path.startswith(self.prefix):
            return NailgunStaticApp(environ, start_response)
        else:
            return self.app(environ, start_response)

    def normpath(self, path):
        path2 = os.path.normpath(urllib.unquote(path))
        if path.endswith("/"):
            path2 += "/"
        return path2
