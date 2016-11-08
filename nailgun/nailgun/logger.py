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

import logging
import re
import sys

from logging.handlers import WatchedFileHandler
from StringIO import StringIO


SERVER_ERROR_MSG = '500 Internal Server Error'
DATEFORMAT = '%Y-%m-%d %H:%M:%S'
LOGFORMAT = '%(asctime)s.%(msecs)03d %(levelname)s ' + \
            '[%(thread)x] (%(module)s) %(message)s'
formatter = logging.Formatter(LOGFORMAT, DATEFORMAT)
nodes_agent_uri = re.compile('/api/(v[0-9]+/)?nodes/agent/')


# NOTE(aroma): the logging level for nailgun is set up inside
# nailgun settings parsing object in nailgun.settings module hence
# following option will be in effect only when the settings are not
# available for some reason
LOG_LEVEL = logging.DEBUG


def make_nailgun_logger():
    """Make logger for nailgun app writes logs to stdout"""
    logger = logging.getLogger("nailgun")
    handler = logging.StreamHandler(sys.stdout)
    set_logger(logger, handler)
    return logger


def make_file_logger(name, filename):
    logger = logging.getLogger(name)
    log_file = WatchedFileHandler(filename)
    set_logger(logger, log_file)
    return logger


def make_api_logger():
    """Make logger for REST API writes logs to the file"""
    # Circular import dependency problem
    # we import logger module in settings
    from nailgun.settings import settings
    return make_file_logger("nailgun-api", settings.API_LOG)


def make_api_nodes_agent_logger():
    """Logger that store node data POST and PUT over REST API"""
    # Circular import dependency problem
    # we import logger module in settings
    from nailgun.settings import settings
    return make_file_logger(
        "nailgun-api-nodes-agent",
        settings.API_NODES_AGENT_LOG
    )


def set_logger(logger, handler, level=None):
    if level is None:
        level = LOG_LEVEL

    handler.setFormatter(formatter)

    logger.setLevel(level)
    logger.addHandler(handler)


logger = make_nailgun_logger()


class WriteLogger(logging.Logger, object):

    def __init__(self, logger, level=logging.DEBUG):
        super(WriteLogger, self).__init__(logger)
        self.logger = logger

    def write(self, message):
        if message.strip() != '':
            self.logger(message)


class HTTPLoggerMiddleware(object):
    def __init__(self, application):
        self.application = application
        self.api_logger = make_api_logger()
        self.api_nodes_agent_logger = make_api_nodes_agent_logger()

    def __call__(self, env, start_response):
        env['wsgi.errors'] = WriteLogger(self.api_logger.error)
        self.__logging_request(env)

        def start_response_with_logging(status, headers, *args):
            self.__logging_response(env, status)
            return start_response(status, headers, *args)

        return self.application(env, start_response_with_logging)

    def __get_api_logger(self, env):
        if (env['REQUEST_METHOD'] in ("POST", "PUT") and
           nodes_agent_uri.match(env['REQUEST_URI'])):
            return self.api_nodes_agent_logger
        else:
            return self.api_logger

    def __logging_response(self, env, response_code):
        response_info = "Response code '%s' for %s %s from %s:%s" % (
            response_code,
            env['REQUEST_METHOD'],
            env['REQUEST_URI'],
            self.__get_remote_ip(env),
            env['REMOTE_PORT'],
        )

        if response_code == SERVER_ERROR_MSG:
            self.__get_api_logger(env).error(response_info)
        else:
            self.__get_api_logger(env).debug(response_info)

    def __logging_request(self, env):
        content_length = env.get('CONTENT_LENGTH', 0)
        if content_length == '':
            content_length = 0
        length = int(content_length)
        body = ''

        if length != 0:
            body = env['wsgi.input'].read(length)
            env['wsgi.input'] = StringIO(body)

        request_info = "Request %s %s from %s:%s %s" % (
            env['REQUEST_METHOD'],
            env['REQUEST_URI'],
            self.__get_remote_ip(env),
            env['REMOTE_PORT'],
            body
        )

        self.__get_api_logger(env).debug(request_info)

    def __get_remote_ip(self, env):
        if 'HTTP_X_REAL_IP' in env:
            return env['HTTP_X_REAL_IP']
        elif 'REMOTE_ADDR' in env:
            return env['REMOTE_ADDR']
        else:
            return 'can not determine ip'
