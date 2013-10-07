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
from web.httpserver import StaticMiddleware
from web.httpserver import WSGIServer

curdir = os.path.dirname(__file__)
sys.path.insert(0, curdir)

from nailgun.api.handlers import forbid_client_caching
from nailgun.db import engine
from nailgun.db import load_db_driver
from nailgun.logger import HTTPLoggerMiddleware
from nailgun.logger import logger
from nailgun.settings import settings
from nailgun.urls import urls


def build_app():
    app = web.application(urls, locals())
    app.add_processor(load_db_driver)
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
    func = StaticMiddleware(func)
    server = WSGIServer(server_address, func)
    print('http://%s:%d/' % server_address)

    try:
        server.start()
    except (KeyboardInterrupt, SystemExit):
        server.stop()


def appstart(keepalive=False):
    logger.info("Fuel-Web {0} SHA: {1}\nFuel SHA: {2}".format(
        settings.VERSION['release'],
        settings.VERSION['nailgun_sha'],
        settings.VERSION['fuellib_sha'],
        settings.VERSION['ostf_sha']
    ))
    if not engine.dialect.has_table(engine.connect(), "nodes"):
        logger.error(
            "Database tables not created. Try './manage.py syncdb' first"
        )
        sys.exit(1)

    web.config.debug = bool(settings.DEVELOPMENT)
    app = build_app()

    from nailgun.keepalive import keep_alive
    from nailgun.rpc import threaded

    if keepalive:
        logger.info("Running KeepAlive watcher...")
        keep_alive.start()

    if not settings.FAKE_TASKS:
        if not keep_alive.is_alive() \
                and not settings.FAKE_TASKS_AMQP:
            logger.info("Running KeepAlive watcher...")
            keep_alive.start()
        rpc_process = threaded.RPCKombuThread()
        logger.info("Running RPC consumer...")
        rpc_process.start()
    logger.info("Running WSGI app...")

    wsgifunc = build_middleware(app.wsgifunc)

    run_server(wsgifunc,
               (settings.LISTEN_ADDRESS, int(settings.LISTEN_PORT)))

    logger.info("Stopping WSGI app...")
    if keep_alive.is_alive():
        logger.info("Stopping KeepAlive watcher...")
        keep_alive.join()
    if not settings.FAKE_TASKS:
        logger.info("Stopping RPC consumer...")
        rpc_process.join()
    logger.info("Done")
