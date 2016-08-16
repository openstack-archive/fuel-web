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

from nailgun.utils.uniondict import UnionDict


class TransactionContext(object):
    def __init__(self, new_state, old_state=None, **kwargs):
        """Wrapper around current and previous state of a transaction

        :param new_state: new state of cluster
                          {node_id: <deployment info>, ...}
        :param old_state: old state of cluster per task name or None
                          {task_id: {node_id: <deployment info>, ...}, ...}
        """
        self.new = new_state
        self.old = old_state or {}
        self.options = kwargs

    def get_new_data(self, node_id):
        return UnionDict(self.new['common_attrs'],
                         self.new['nodes'][node_id])

    def get_old_data(self, node_id, task_id):
        dinfo = self.old.get(task_id, {})
        if not dinfo or not dinfo['nodes'].get(node_id):
            return {}
        else:
            return UnionDict(dinfo['common_attrs'],
                             dinfo['nodes'].get(node_id, {}))
