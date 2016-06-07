#    Copyright 2016 Mirantis, Inc.
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


RESERVED_COMMANDS = {
    ':show cluster': 'show_cluster',
    ':use cluster': 'use_cluster',
    ':show tasks': 'show_tasks',
    ':oldcontext task': 'use_old_context_from_task',
    ':newcontext task': 'use_new_context_from_task',
    ':show nodes': 'show_nodes',
    ':show node': 'show_current_node',
    ':use node': 'use_node',
}
