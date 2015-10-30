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

from nailgun import consts


class TaskHelper(object):
    """Helper methods for upgrade routines."""

    @classmethod
    def _is_controller(cls, node):
        return (node.status == consts.NODE_STATUSES.ready and
                node.roles.any('controller'))

    @classmethod
    def nodes_to_upgrade(cls, cluster):
        """List nodes that constitute the new control plane

        At least one controller (with minimal ID) has to be
        upgraded to update version of control plane.

        :param cluster: the cluster picked for upgrade
        :type cluster:  instance of :class:`nailgun.objects.Cluster`
        :returns:       nailgun.objects.Node object for primary
                        controller
        """
        nodes = six.moves.filter(cls._is_controller, cluster.nodes)
        node_to_upgrade = min(nodes, key=lambda n: n.id)
        return [node_to_upgrade]
