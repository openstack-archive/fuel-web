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

from nailgun import objects

from nailgun.logger import logger
from nailgun.openstack.common import jsonutils
from nailgun.task.helpers import TaskHelper


__all__ = ['Check']


class Check(object):

    def __init__(self, data):
        logger.info(
            "RPC method verify_networks_resp received: %s" %
            jsonutils.dumps(data)
        )
        self.task_uuid = data.get('task_uuid')
        self.nodes = data.get('nodes')
        self.error_msg = data.get('error')
        self.status = data.get('status')
        self.progress = data.get('progress')
        self.task = objects.Task.get_by_uuid(self.task_uuid)
        self.context = {}
        self.result = []

    def run(self):
        if self.status == 'error':
            self._set_error()
        elif self.nodes is None:
            pass
        elif isinstance(self.nodes, list):
            self._verify_nodes()
        else:
            error_msg = ('verify_networks_resp: argument "nodes"'
                         ' have incorrect type')
            self._set_error(error_msg)
        self._update()

    def _set_error(self, error_msg=None):
        # There is existing test for verification that custom error
        # message should be prioritized
        self.error_msg = self.error_msg or error_msg
        self.status = 'error'
        logger.warning(error_msg)

    def _update(self):
        if self.result:
            self._set_error()
        if self.status not in ('ready', 'error'):
            TaskHelper.update_task_status(
                self.task_uuid, self.status,
                self.progress, self.error_msg, self.result)
        else:
            TaskHelper.update_verify_networks(
                self.task_uuid, self.status, self.progress,
                self.error_msg, self.result)

    def _verify_forgotten_nodes(self, uids):
        absent_nodes = objects.NodeCollection.filter_by_id_list(None, uids)
        absent_node_names = []
        for n in absent_nodes:
            if n.name:
                absent_node_names.append(n.name)
            else:
                absent_node_names.append('id: %s' % n.id)
        error_msg = 'Node(s) {0} didn\'t return data.'.format(
            ', '.join(absent_node_names)
        )
        self._set_error(error_msg)

    def _verify_received_node(self, node, cached_node):
        for cached_network in cached_node['networks']:

            data = {}

            received_networks_filtered = filter(
                lambda n: n['iface'] == cached_network['iface'],
                node.get('networks', [])
            )
            if received_networks_filtered:
                received_network = received_networks_filtered[0]
                absent_vlans = list(
                    set(cached_network['vlans']) -
                    set(received_network['vlans'])
                )
            else:
                logger.warning(
                    "verify_networks_resp: arguments don't contain"
                    " data for interface: uid=%s iface=%s",
                    node['uid'], cached_network['iface']
                )
                absent_vlans = cached_network['vlans']

            if absent_vlans:
                data['uid'] = node['uid']
                data['absent_vlans'] = absent_vlans
                data['interface'] = cached_network['iface']
                node_db = objects.Node.get_by_uid(node['uid'])
                if node_db:
                    data['name'] = node_db.name
                    db_nics = filter(
                        lambda i:
                        i.name == cached_network['iface'],
                        node_db.nic_interfaces
                    )
                    if db_nics:
                        nic = db_nics[0]
                        data['mac'] = nic.mac
                    else:
                        logger.warning(
                            "verify_networks_resp: can't find "
                            "interface %r for node %r in DB",
                            cached_network['iface'], node_db.id
                        )
                        data['mac'] = 'unknown'
                else:
                    logger.warning(
                        "verify_networks_resp: can't find node "
                        "%r in DB",
                        node['uid']
                    )
                self.result.append(data)

    def _verify_received_nodes(self, cached_nodes):
        for node in self.nodes:
            cached_nodes_filtered = filter(
                lambda n: str(n['uid']) == str(node['uid']),
                cached_nodes
            )

            if cached_nodes_filtered:
                cached_node = cached_nodes_filtered[0]
                self._verify_received_node(node, cached_node)
            else:
                logger.warning(
                    "verify_networks_resp: arguments contain node "
                    "data which is not in the task cache: %r",
                    node
                )

    def _verify_nodes(self):
        #  We expect that 'nodes' contains all nodes which we test.
        #  Situation when some nodes not answered must be processed
        #  in orchestrator early.
        cached_nodes = self.task.cache['args']['nodes']
        node_uids = [str(n['uid']) for n in self.nodes]
        cached_node_uids = [str(n['uid']) for n in cached_nodes]
        forgotten_uids = set(cached_node_uids) - set(node_uids)

        if forgotten_uids:
            self._verify_forgotten_nodes(forgotten_uids)
        else:
            self._verify_received_nodes(cached_nodes)
