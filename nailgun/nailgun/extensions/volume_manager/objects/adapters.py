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


class NailgunNodeAdapter(object):

    def __init__(self, node):
        self.node = node

    @property
    def id(self):
        return self.node.id

    @property
    def name(self):
        return self.node.name

    @property
    def full_name(self):
        return self.node.full_name

    def get_node_spaces(self):
        from nailgun.extensions.volume_manager.manager import get_node_spaces

        # If node bound to the cluster than it has a role
        # and volume groups which we should to allocate
        if self.node.cluster:
            return get_node_spaces(self.node)
        return []

    @property
    def disks(self):
        return self.node.meta['disks']

    @property
    def ram(self):
        return self.node.meta['memory']['total']

    @property
    def is_ubuntu(self):
        """Returns True if node OS is Ubuntu, False otherwise"""
        return (self.node.cluster and
                self.node.cluster.release.operating_system.lower() == "ubuntu")
