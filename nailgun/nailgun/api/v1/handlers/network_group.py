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


import web

from nailgun.api.v1.handlers.base import CollectionHandler
from nailgun.api.v1.handlers.base import content
from nailgun.api.v1.handlers.base import SingleHandler
from nailgun.api.v1.validators.base import BasicValidator

from nailgun import objects

from nailgun.db import db


class NetworkGroupHandler(SingleHandler):
    """Network group handler
    """

    validator = BasicValidator
    single = objects.NetworkGroup

    fields = ('id', 'name', 'release', 'group_id', 'vlan_start',
              'cidr', 'gateway', 'meta')

    @content
    def PUT(self, net_id):
        net = self.get_object_or_404(objects.NetworkGroup, net_id)
        data = self.validator.validate(web.data())

        self.single.update(net, data)
        return self.render(net)

    def DELETE(self, net_id):
        net = self.get_object_or_404(objects.NetworkGroup, net_id)
        self.single.delete(net)

        raise self.http(204)


class NetworkGroupCollectionHandler(CollectionHandler):

    collection = objects.NetworkGroupCollection
    validator = BasicValidator
