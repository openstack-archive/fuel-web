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

from copy import deepcopy

from ..models.node_volumes import NodeVolumes
from nailgun.db import db


class VolumeObject(object):
    """Here we keep buisness logic which is related to
    volumes configuration
    """

    @classmethod
    def get_volumes(cls, node):
        """Retrieves volumes

        :param node: node object
        :returns: volumes for the node
        """
        volumes_db = cls._get_model_by_node_id(node.id)
        if volumes_db:
            return volumes_db.volumes

        return None

    @classmethod
    def set_volumes(cls, node, volumes):
        """Sets volumes

        :param node: node object
        :param volumes: volumes for node
        :returns: volumes
        """
        volume_db = cls._get_model_by_node_id(node.id)

        if volume_db:
            volume_db.volumes = deepcopy(volumes)
        else:
            volumes = NodeVolumes(node_id=node.id, volumes=volumes)
            db().add(volumes)

        db().flush()

        return volumes

    @classmethod
    def _get_model_by_node_id(cls, node_id):
        """Retrieves NodeVolumes model by id

        :param int node_id: id of node in volumes table
        :returns: NodeVolumes model
        """
        return db().query(NodeVolumes).filter_by(node_id=node_id).first()
