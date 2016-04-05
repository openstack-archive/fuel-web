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

from .base import DiskException
from .base import ExpressionParserException
from .base import ExtensionException
from .base import MongoException
from .base import NailgunException
from .base import NetworkException
from .base import NodeDiscoveringException
from .base import PluginException
from .base import ApiException
from .base import RPCException
from .base import TaskException
from .base import UnhandledException
from .base import ValidationException
from .base import ZabbixException

from .api import *
from .deployment import *
from .disk import *
from .extension import *
from .mongodb import *
from .network import *
from .node import *
from .parses import *
from .plugins import *
from .validation import *
from .zabbix import *


class UnresolvableConflict(UnhandledException):
    message = "Unresolvable conflict"


class NodeNotBelongToCluster(UnhandledException):
    message = "The Node doesn't belong to the Cluster"


class NoChanges(TaskException):
    message = "There is no changes to apply"


class CannotFindTask(RPCException):
    message = "Cannot find task"
