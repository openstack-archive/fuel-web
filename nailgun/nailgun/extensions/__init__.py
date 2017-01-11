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
from nailgun.extensions.base import BasePipeline
from nailgun.extensions.manager import callback_wrapper
from nailgun.extensions.manager import get_extension
from nailgun.extensions.manager import get_all_extensions
from nailgun.extensions.manager import fire_callback_on_before_deployment_check
from nailgun.extensions.manager import fire_callback_on_node_delete
from nailgun.extensions.manager import fire_callback_on_node_collection_delete
from nailgun.extensions.manager import fire_callback_on_node_create
from nailgun.extensions.manager import fire_callback_on_node_update
from nailgun.extensions.manager import fire_callback_on_node_reset
from nailgun.extensions.manager import fire_callback_on_nodegroup_create
from nailgun.extensions.manager import fire_callback_on_nodegroup_delete
from nailgun.extensions.manager import fire_callback_on_cluster_create
from nailgun.extensions.manager import fire_callback_on_cluster_delete
from nailgun.extensions.manager import fire_callback_on_remove_node_from_cluster
from nailgun.extensions.manager import \
    fire_callback_on_before_deployment_serialization
from nailgun.extensions.manager import \
    fire_callback_on_before_provisioning_serialization
from nailgun.extensions.manager import \
    fire_callback_on_cluster_patch_attributes
from nailgun.extensions.manager import \
    fire_callback_on_cluster_serialization_for_deployment
from nailgun.extensions.manager import \
    fire_callback_on_node_serialization_for_deployment
from nailgun.extensions.manager import \
    fire_callback_on_cluster_serialization_for_provisioning
from nailgun.extensions.manager import \
    fire_callback_on_node_serialization_for_provisioning
from nailgun.extensions.manager import node_extension_call
from nailgun.extensions.manager import remove_extensions_from_object
from nailgun.extensions.manager import setup_yaql_context
from nailgun.extensions.manager import update_extensions_for_object
