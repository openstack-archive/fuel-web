# coding: utf-8

# Copyright 2016 Mirantis, Inc.
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

import collections
import copy

__all__ = ['distribute_hugepages']


class NumaNode(object):
    def __init__(self, id_, memory):
        """NumaNode helper class for data manipulation.

        id_: numa node id
        memory: numa node memory in KiBs
        """
        self.id = id_
        self.free_memory = memory
        self.pages = collections.defaultdict(int)

    def allocate(self, component):
        """Allocate memory for component on this node.

        Return True if pages allocation was successfull for component.
        Also changes component state inplace.
        """
        if component.is_done():
            return True

        allocated = False

        for page_size, _ in component.pages():
            # calculate pages count that we can allocate with this
            # size on this numa node
            available = self.free_memory // page_size
            allocated_pages = component.allocate(page_size, available)

            if allocated_pages:
                self.pages[page_size] += allocated_pages
                self.free_memory -= page_size * allocated_pages
                allocated = True

        return allocated

    def report(self):
        result = []

        for size, count in sorted(self.pages.items()):
            result.append({'count': count,
                           'numa_id': self.id,
                           'size': size})

        return result


class Component(object):
    """Helper class for data manipulation.

    Represents one of the components that need hugepages (such as dpdk)
    """

    def __init__(self, pages_info):
        """Get pages info that component requires.

        pages_info: dict with pages sizes and counts.
        Example: {'2048': 1, '1048576': 2}
        """
        pages = [(int(size), count)
                 for size, count in pages_info.items() if count != 0]

        # sort by page size from bigger to smaller
        # That required by greedy algorithm. We trying to allocate big
        # pages first to avoid situation when you have a lot of free
        # memory in total, but can't allocate 1GiB page on any numa node
        pages.sort(reverse=True)
        self._pages = collections.OrderedDict(pages)

    def allocate(self, page_size, pages_available):
        """Allocate component's pages of size page_size.

        page_size: size of pages to allocate (in KiBs)
        pages_available: avalible pages of this size on numa node

        Return count of pages that was really allocated.
        """
        pages = self._pages

        if page_size not in pages:
            return 0

        required = pages[page_size]
        limit = min(required, pages_available)
        pages[page_size] -= limit

        if pages[page_size] == 0:
            pages.pop(page_size)

        return limit

    def pages(self):
        return self._pages.items()

    def is_done(self):
        return not self._pages


def distribute_hugepages(numa_topology, components):
    all_comps = [Component(comp) for comp in components['all']]
    any_comps = [Component(comp) for comp in components['any']]

    numa_nodes = []
    for numa_node in numa_topology['numa_nodes']:
        # converting memory to KiBs
        memory = numa_node['memory'] // 1024

        # for the first numa node reserve 1GiB memory for operating system
        if numa_node['id'] == 0:
            memory -= 2 ** 20

        numa_nodes.append(NumaNode(numa_node['id'], memory))

    _allocate_all(numa_nodes, all_comps)
    _allocate_any(numa_nodes, any_comps)

    return sum([n.report() for n in numa_nodes], [])


def _allocate_all(numa_nodes, components):
    """Allocate every component on all numa nodes."""
    for component in components:
        for numa_node in numa_nodes:
            comp = copy.deepcopy(component)
            allocated = numa_node.allocate(comp)
            if not (allocated and comp.is_done()):
                # this situation should be validated by API
                raise ValueError('Components that must be allocated on every'
                                 ' numa node could not require more memory'
                                 ' than node has.')


def _allocate_any(numa_nodes, components):
    """Allocate every component on some numa nodes.

    For now we don't make a distinction between components so just
    merge them in big one and try to allocate on nodes.

    """
    comp = _merge_components(components)

    for numa_node in numa_nodes:
        numa_node.allocate(comp)
        if comp.is_done():
            break
    else:
        # This situation shoul be validated by API
        # if we check all nodes with same component and not found
        # free memory for allocation then raise error
        raise ValueError('Not enough memory for components that can be'
                         ' allocated on any NUMA node.')


def _merge_components(components):
    res = collections.defaultdict(int)
    for comp in components:
        for size, count in comp.pages():
            res[size] += count

    return Component(res)
