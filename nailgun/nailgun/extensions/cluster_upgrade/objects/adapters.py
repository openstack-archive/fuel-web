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

from nailgun import objects


class NailgunClusterAdapter(object):
    def __init__(self, cluster):
        self.cluster = cluster

    @property
    def id(self):
        return self.cluster.id

    @property
    def generated_attrs(self):
        return self.cluster.attributes.generated

    @generated_attrs.setter
    def generated_attrs(self, attrs):
        self.cluster.attributes.generated = attrs

    @property
    def editable_attrs(self):
        return self.cluster.attributes.editable

    @editable_attrs.setter
    def editable_attrs(self, attrs):
        self.cluster.attributes.editable = attrs

    def get_create_data(self):
        return objects.Cluster.get_create_data(self.cluster)
