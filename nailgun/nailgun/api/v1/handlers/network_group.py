# -*- coding: utf-8 -*-

#    Copyright 2015 Mirantis, Inc.
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


from nailgun.api.v1.handlers.base import CollectionHandler
from nailgun.api.v1.handlers.base import SingleHandler
from nailgun.api.v1.validators.network import NetworkGroupValidator

from nailgun import objects


class NetworkGroupHandler(SingleHandler):
    """Network group handler
    """

    validator = NetworkGroupValidator
    single = objects.NetworkGroup


class NetworkGroupCollectionHandler(CollectionHandler):
    """Network group collection handler
    """

    collection = objects.NetworkGroupCollection
    validator = NetworkGroupValidator
