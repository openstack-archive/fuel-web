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

from nailgun.extensions.base import BaseExtension
from nailgun.extensions.base import BaseExtensionPipeline
from nailgun.extensions.manager import get_extension
from nailgun.extensions.manager import get_all_extensions
from nailgun.extensions.manager import node_extension_call
from nailgun.extensions.manager import fire_callback_on_node_delete
from nailgun.extensions.manager import fire_callback_on_node_collection_delete
from nailgun.extensions.manager import fire_callback_on_node_create
from nailgun.extensions.manager import fire_callback_on_node_update
from nailgun.extensions.manager import fire_callback_on_node_reset
from nailgun.extensions.manager import fire_callback_on_cluster_delete
from nailgun.extensions.manager import \
    fire_callback_on_deployment_data_serialization
from nailgun.extensions.manager import \
    fire_callback_on_provisioning_data_serialization
