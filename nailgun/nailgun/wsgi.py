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

curdir = os.path.dirname(__file__)
sys.path.insert(0, curdir)

from nailgun.api.handlers import forbid_client_caching
from nailgun.api.handlers import load_db_driver
from nailgun.db import engine
from nailgun.logger import HTTPLoggerMiddleware
from nailgun.logger import logger
from nailgun.settings import settings
from nailgun.urls import urls


def build_app(db_driver=None):
    """Build app and disable debug mode in case of production
    """
    web.config.debug = bool(int(settings.DEVELOPMENT))
    app = web.application(urls(), locals())
    app.add_processor(db_driver or load_db_driver)
    app.add_processor(forbid_client_caching)
    return app


def build_middleware(app):
    middleware_list = [
        HTTPLoggerMiddleware
    ]

    logger.debug('Initialize middleware: %s' %
                 (map(lambda x: x.__name__, middleware_list)))

    return app(*middleware_list)


def run_server(func, server_address=('0.0.0.0', 8080)):
    """This function same as runsimple from web/httpserver
    except removed LogMiddleware because we use
    HTTPLoggerMiddleware instead
    """
    global server
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

    app = build_app()

    wsgifunc = build_middleware(app.wsgifunc)

    run_server(wsgifunc,
               (settings.LISTEN_ADDRESS, int(settings.LISTEN_PORT)))

    logger.info("Stopping WSGI app...")
    logger.info("Done")


application = build_middleware(build_app().wsgifunc)
