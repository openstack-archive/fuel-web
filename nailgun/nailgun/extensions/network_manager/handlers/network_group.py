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
from nailgun.api.v1.handlers.base import handle_errors
from nailgun.api.v1.handlers.base import serialize
from nailgun.api.v1.handlers.base import SingleHandler
from nailgun.api.v1.handlers.base import validate
from nailgun.extensions.network_manager.validators.network import \
    NetworkGroupValidator
from nailgun.logger import logger

from nailgun import errors
from nailgun import objects


def check_if_network_configuration_locked(node_group):
    if (node_group and
       objects.Cluster.is_network_modification_locked(node_group.cluster)):
        raise SingleHandler.http(403,
                                 "Network configuration cannot be changed "
                                 "during deployment and after upgrade.")


class NetworkGroupHandler(SingleHandler):
    """Network group handler"""

    validator = NetworkGroupValidator
    single = objects.NetworkGroup

    @handle_errors
    @validate
    @serialize
    def PUT(self, group_id):
        """:returns: JSONized Network Group object.

        :http:
            * 200 (OK)
            * 400 (error occured while processing of data)
            * 403 (change of configuration is forbidden)
            * 404 (Network group was not found in db)
        """
        ng = self.get_object_or_404(self.single, group_id)
        check_if_network_configuration_locked(ng.nodegroup)

        data = self.checked_data(
            self.validator.validate_update,
            instance=ng
        )
        self.single.update(ng, data)

        return self.single.to_dict(ng)

    @handle_errors
    @validate
    def DELETE(self, group_id):
        """Remove Network Group

        :http:
            * 204 (object successfully deleted)
            * 400 (cannot delete object)
            * 403 (change of configuration is forbidden)
            * 404 (no such object found)
        """
        ng = self.get_object_or_404(self.single, group_id)
        check_if_network_configuration_locked(ng.nodegroup)

        self.checked_data(
            self.validator.validate_delete,
            instance=ng
        )

        self.single.delete(ng)
        raise self.http(204)


class NetworkGroupCollectionHandler(CollectionHandler):
    """Network group collection handler"""

    collection = objects.NetworkGroupCollection
    validator = NetworkGroupValidator

    @handle_errors
    @validate
    def POST(self):
        """:returns: JSONized Network Group object.

        :http: * 201 (network group successfully created)
               * 400 (invalid object data specified)
               * 403 (change of configuration is forbidden)
               * 409 (network group already exists)
        """

        data = self.checked_data()
        node_group = objects.NodeGroup.get_by_uid(data.get('group_id'))
        check_if_network_configuration_locked(node_group)

        try:
            new_ng = self.collection.create(data)
        except errors.CannotCreate as exc:
            logger.exception("Network group creation failed")
            raise self.http(400, exc.message)

        raise self.http(201, self.collection.single.to_json(new_ng))
