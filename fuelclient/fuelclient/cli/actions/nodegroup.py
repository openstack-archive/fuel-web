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

from fuelclient.cli.actions.base import Action
from fuelclient.cli.actions.base import check_all
import fuelclient.cli.arguments as Args
from fuelclient.cli.arguments import group
from fuelclient.cli.error import ActionException
from fuelclient.cli.formatting import format_table
from fuelclient.objects.node import Node
from fuelclient.objects.nodegroup import NodeGroup
from fuelclient.objects.nodegroup import NodeGroupCollection


class NodeGroupAction(Action):
    """Show or modify node groups
    """
    action_name = "nodegroup"
    acceptable_keys = ("id", "cluster", "name")

    def __init__(self):
        super(NodeGroupAction, self).__init__()
        self.args = (
            Args.get_env_arg(),
            Args.get_list_arg("List all node groups."),
            Args.get_name_arg("Name of new node group."),
            Args.get_group_arg("ID of node group."),
            Args.get_node_arg("List of nodes to assign specified group to."),
            group(
                Args.get_create_arg(
                    "Create a new node group in the specified environment."
                ),
                Args.get_assign_arg(
                    "Download current network configuration."),
                Args.get_delete_arg(
                    "Verify current network configuration."),
            )
        )
        self.flag_func_map = (
            ("create", self.create),
            ("delete", self.delete),
            ("assign", self.assign),
            (None, self.list)
        )

    def create(self, params):
        """Create a new node group
               fuel --env 1 nodegroup --create --name "group 1"
        """
        NodeGroup.create(params.name, int(params.env))

    def delete(self, params):
        """Delete the specified node groups
               fuel --env 1 nodegroup --delete --group 1
               fuel --env 1 nodegroup --delete --group 2,3,4
        """
        ngs = NodeGroup.get_by_ids(params.group)
        for n in ngs:
            if n.name == "default":
                raise ActionException(
                    "Default node groups cannot be deleted."
                )
            NodeGroup.delete(n.id)

    @check_all("env")
    def assign(self, params):
        """Assign nodes to specified node group:
                fuel --env 1 nodegroup --assign --node 1 --group 1
                fuel --env 1 nodegroup --assign --node 2,3,4 --group 1
        """
        nodes = [n.id for n in map(Node, params.node)]
        ngs = map(NodeGroup, params.group)
        if len(ngs) > 1:
            raise ActionException(
                "Nodes can only be assigned to one node group."
            )
        NodeGroup.assign(ngs[0].id, nodes)

    def list(self, params):
        """To list all available node groups:
                fuel nodegroup

            To filter them by environment:
                fuel --env-id 1 nodegroup
        """
        group_collection = NodeGroupCollection.get_all()
        if params.env:
            group_collection.filter_by_env_id(int(params.env))
        self.serializer.print_to_output(
            group_collection.data,
            format_table(
                group_collection.data,
                acceptable_keys=self.acceptable_keys,
            )
        )
