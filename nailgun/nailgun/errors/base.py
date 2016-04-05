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

import six

from nailgun.logger import logger


@six.python_2_unicode_compatible
class NailgunException(Exception):

    def __init__(self,
                 message="",
                 log_traceback=False,
                 log_message=False,
                 log_level='warning'):
        self.log_traceback = log_traceback
        self.log_message = log_message
        if message:
            self.message = message
            if self.log_message:
                getattr(logger, log_level)(self.message)

        super(NailgunException, self).__init__()

    def __str__(self):
        return '{0}("{1}")'.format(
            self.__class__.__name__,
            self.message
        )

    __repr__ = __str__


class TaskException(NailgunException):
    message = "Base task exception"


class NetworkException(NailgunException):
    message = "Base network exception"


class RESTException(NailgunException):
    message = "Base REST exception"


class NodeDiscoveringException(NailgunException):
    message = "Base node discovering exception"


class DiskException(NailgunException):
    message = "Base disk exception"


class MongoException(NailgunException):
    message = "Base mongodb exception"


class RPCException(NailgunException):
    message = "Base RPC exception"


class ExpressionParserException(NailgunException):
    message = "Base expression parser exception"


class ZabbixException(NailgunException):
    message = "Base zabbix exception"


class PluginException(NailgunException):
    message = "Base plugn exception"


class ExtensionException(NailgunException):
    message = "Base extension exception"


class UnhandledException(NailgunException):
    message = "Base unhandled exception"


class ValidationException(NailgunException):
    message = "Base validateion exception"
