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
import itertools

__all__ = ['distribute_hugepages']


class NumaNode(object):
    def __init__(self, id_, memory):
        self.id = id_
        self.free_memory = memory
        self.pages = collections.defaultdict(int)

    def allocate(self, component):
        if component.is_done():
            return True

        allocated = False

        for page_size, pages_required in component.pages():
            # calculate pages count that we can allocate with this
            # size on this numa node
            available = self.free_memory // page_size

            if available == 0:
                continue

            if available >= pages_required:
                limit = pages_required
            else:
                limit = available

            self.pages[page_size] += limit
            self.free_memory -= page_size * limit
            component.allocate(page_size, limit)
            allocated = True

        return allocated

    def report(self):
        return [{'count': count,
                 'numa_id': self.id,
                 'size': self._format_size(size)}
                for size, count in sorted(self.pages.items()) if count != 0]

    def _format_size(self, size_in_bytes):
        return str(size_in_bytes // 1024)


class Component(object):
    def __init__(self, value):
        pages = [(int(size) * 1024, int(count))
                 for size, count in value.items() if int(count) != 0]

        # sort by page size from bigger to smaller
        pages.sort(reverse=True)
        self._pages = collections.OrderedDict(pages)

    def allocate(self, page_size, pages_count):
        pages = self._pages

        assert pages.get(page_size, 0) >= pages_count
        pages[page_size] -= pages_count

        if pages[page_size] == 0:
            pages.pop(page_size)

    def pages(self):
        return self._pages.items()

    def is_done(self):
        return self._pages == {}


def distribute_hugepages(numa_topology, components):
    # split components to 2 groups:
    # components that shoud have pages on all numa nodes (such as dpdk)
    # and components that have pages on any numa node
    all_comps = []
    any_comps = []
    for name, attrs in components.items():
        if attrs.get('type') == 'text':
            all_comps.append(Component({'2048': attrs['value']}))

        elif attrs.get('type') == 'custom_hugepages':
            any_comps.append(Component(attrs['value']))

    numa_nodes = [NumaNode(n['id'], n['memory'])
                  for n in numa_topology['numa_nodes']]

    _allocate_all(numa_nodes, all_comps)
    _allocate_any(numa_nodes, any_comps)

    return sum([n.report() for n in numa_nodes], [])


def _allocate_all(numa_nodes, components):
    for component in components:
        for nnode in numa_nodes:
            comp = copy.deepcopy(component)
            allocated = nnode.allocate(comp)
            assert allocated and comp.is_done()


def _allocate_any(numa_nodes, components):
    nodes_count = len(numa_nodes)

    numa_nodes = itertools.cycle(numa_nodes)
    components = iter(components)

    nnode = next(numa_nodes)
    comp = next(components)

    counter = 0
    while counter <= nodes_count:
        allocated = nnode.allocate(comp)

        if comp.is_done():
            try:
                comp = next(components)
                counter = 0
            except StopIteration:
                break

        if not allocated:
            nnode = next(numa_nodes)
            counter += 1
    else:
        # if we check all nodes with same component and not found
        # free memory for allocation then raise error
        raise ValueError('Not enough memory for components')
