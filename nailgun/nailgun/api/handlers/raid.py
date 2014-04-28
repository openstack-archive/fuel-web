# -*- coding: utf-8 -*-

#    Copyright 2014 Mirantis, Inc.
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

"""
Handlers dealing with RAIDs
"""

from nailgun.api.handlers.base import BaseHandler
from nailgun.api.handlers.base import content_json


class NodeRaidHandler(BaseHandler):
    """Node RAID configuration handler
    """

    @content_json
    def GET(self, node_id):
        """:returns: Current node's RAID configuration."""
        return {'ok': 'fake'}

    @content_json
    def PUT(self, node_id):
        """Update node RAID configuration."""
        return {'ok': 'fake'}


class NodeDefaultsRaidHandler(BaseHandler):
    """Node default RAID handler
    """

    @content_json
    def GET(self, node_id):
        """:returns: JSONized RAID configuration.
        """

        return {'ok': 'fake'}


class NodeRaidApplyHandler(BaseHandler):
    """Node RAID configration applying handler
    """

    @content_json
    def GET(self, node_id):
        """:returns: Current node's RAID configration in a way
        that it will be sent to Astute
        """
        return {'ok': 'fake'}

    @content_json
    def PUT(self, node_id):
        """Trigger applying of the node's RAID configuration."""
        return {'ok': 'fake'}
