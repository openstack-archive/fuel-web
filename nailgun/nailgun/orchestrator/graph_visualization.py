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

from networkx.utils import make_str
import pydot_ng as pydot

from nailgun import consts


class GraphVisualization(object):
    """Wrapper for OrchestratorGraph used for graph visualization."""

    def __init__(self, graph):
        self._graph = graph

    def get_dotgraph(self, tasks=None, parents_for=None, remove=None):
        """Get a graph representation in DOT format.

        :param tasks: list of tasks that will be used in deployemnt
        :param parents_for: name of task which parents will be shown
        :param remove: type of tasks to remove from graph visualization
        """
        graph = self._graph.copy()

        if tasks:
            graph.only_tasks(tasks)

        if parents_for:
            parents = graph.predecessors(parents_for)
            parents.append(parents_for)
            graph = graph.subgraph(parents)

        if not remove:
            remove = []

        # NOTE(prmtl) it is not guaranted that node default
        # values will be put on top of DOT file so we must be sure
        # that each node will have correct attributes
        default_node_attrs = {
            'color': 'yellowgreen',
            'style': 'filled'
        }
        type_node_attrs_map = {
            consts.ORCHESTRATOR_TASK_TYPES.group: {
                'color': 'lightskyblue',
                'shape': 'box',
                'style': 'filled, rounded',
            },
            consts.ORCHESTRATOR_TASK_TYPES.skipped: {
                'color': 'gray95',
            },
            consts.ORCHESTRATOR_TASK_TYPES.stage: {
                'shape': 'rect',
                'color': 'red',
                'style': 'filled',
            },
        }

        # set graph attributes for nodes
        for name, data in graph.nodes_iter(data=True):
            task_type = data.get('type')
            if task_type in remove:
                graph.remove_node(name)
                continue
            if data.get('skipped'):
                graph.node[name] = type_node_attrs_map[
                    consts.ORCHESTRATOR_TASK_TYPES.skipped]
            else:
                graph.node[name] = type_node_attrs_map.get(
                    task_type, default_node_attrs)
        return to_pydot(graph)


# NOTE(prmtl): Adapted from networkx library to work with pydot_ng
def to_pydot(N, strict=True):
    """Return a pydot graph from a NetworkX graph N.

    Parameters
    ----------
    N : NetworkX graph
      A graph created with NetworkX

    Examples
    --------
    >>> import networkx as nx
    >>> K5 = nx.complete_graph(5)
    >>> P = nx.to_pydot(K5)

    Notes
    -----


    """
    # set Graphviz graph type
    if N.is_directed():
        graph_type = 'digraph'
    else:
        graph_type = 'graph'
    strict = N.number_of_selfloops() == 0 and not N.is_multigraph()

    name = N.graph.get('name')
    graph_defaults = N.graph.get('graph', {})
    if name is None:
        P = pydot.Dot(graph_type=graph_type, strict=strict, **graph_defaults)
    else:
        P = pydot.Dot('"%s"' % name, graph_type=graph_type, strict=strict,
                      **graph_defaults)
    try:
        P.set_node_defaults(**N.graph['node'])
    except KeyError:
        pass
    try:
        P.set_edge_defaults(**N.graph['edge'])
    except KeyError:
        pass

    for n, nodedata in N.nodes_iter(data=True):
        str_nodedata = dict((k, make_str(v)) for k, v in nodedata.items())
        p = pydot.Node(make_str(n), **str_nodedata)
        P.add_node(p)

    if N.is_multigraph():
        for u, v, key, edgedata in N.edges_iter(data=True, keys=True):
            str_edgedata = dict((k, make_str(v)) for k, v in edgedata.items())
            edge = pydot.Edge(make_str(u), make_str(v),
                              key=make_str(key), **str_edgedata)
            P.add_edge(edge)
    else:
        for u, v, edgedata in N.edges_iter(data=True):
            str_edgedata = dict((k, make_str(v)) for k, v in edgedata.items())
            edge = pydot.Edge(make_str(u), make_str(v), **str_edgedata)
            P.add_edge(edge)
    return P
