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

import os
import sys
import web
from web.httpserver import WSGIServer

sys.path.insert(0, os.path.dirname(__file__))

from nailgun.api.v1.handlers import forbid_client_caching
from nailgun.api.v1.handlers import load_db_driver
from nailgun.db import engine
from nailgun.logger import HTTPLoggerMiddleware
from nailgun.logger import logger
from nailgun.middleware.connection_monitor import ConnectionMonitorMiddleware
from nailgun.middleware.http_method_override import \
    HTTPMethodOverrideMiddleware
from nailgun.middleware.keystone import NailgunFakeKeystoneAuthMiddleware
from nailgun.middleware.keystone import NailgunKeystoneAuthMiddleware
from nailgun.middleware.static import StaticMiddleware
from nailgun.settings import settings
from nailgun.urls import urls


def build_app(db_driver=None):
    """Build app and disable debug mode in case of production
    """
    web.config.debug = bool(int(settings.DEVELOPMENT))
    app = web.application(urls(), locals(),
                          autoreload=bool(int(settings.AUTO_RELOAD)))
    app.add_processor(db_driver or load_db_driver)
    app.add_processor(forbid_client_caching)
    return app


def build_middleware(app):

    middleware_list = [
        ConnectionMonitorMiddleware,
        HTTPLoggerMiddleware,
        HTTPMethodOverrideMiddleware,
    ]

    if settings.DEVELOPMENT:
        middleware_list.append(StaticMiddleware)

    if settings.AUTH['AUTHENTICATION_METHOD'] == 'keystone':
        middleware_list.append(NailgunKeystoneAuthMiddleware)
    elif settings.AUTH['AUTHENTICATION_METHOD'] == 'fake':
        middleware_list.append(NailgunFakeKeystoneAuthMiddleware)

    logger.debug('Initialize middleware: %s' %
                 (map(lambda x: x.__name__, middleware_list)))

    return app(*middleware_list)


def run_server(func, server_address=('0.0.0.0', 8080)):
    """This function same as runsimple from web/httpserver
    except removed LogMiddleware because we use
    HTTPLoggerMiddleware instead
    """
    server = WSGIServer(server_address, func)
    print('http://%s:%d/' % server_address)

    try:
        server.start()
    except (KeyboardInterrupt, SystemExit):
        server.stop()


def appstart():
    logger.info("Fuel version: %s", str(settings.VERSION))
    if not engine.dialect.has_table(engine.connect(), "nodes"):
        logger.error(
            "Database tables not created. Try './manage.py syncdb' first"
        )
        sys.exit(1)

    run_server(build_middleware(build_app().wsgifunc),
               (settings.LISTEN_ADDRESS, int(settings.LISTEN_PORT)))

    logger.info("Stopping WSGI app...")
    logger.info("Done")
