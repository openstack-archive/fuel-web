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

from collections import defaultdict

__all__ = ['distribute_hugepages']


class NumaNode(object):
    def __init__(self, id_, memory):
        self.id = id_
        self.free_memory = memory
        self.pages = defaultdict(int)

    def allocate(self, component):
        allocated = False

        for size, count in component.page.items():
            # calculate pages count that we can allocate with this
            # size on this numa node
            required = size * count
            available = self.free_memory // size

            if available == 0:
                continue

            if available >= required:
                limit = required
            else:
                limit = available

            self.pages[size] += limit
            self.memory -= size * limit
            component.allocate(size, limit)
            allocated = True

        return allocated

    def add_pages(self, page_size, pages_count):
        required = page_size * pages_count

        has_free = self.free_memory >= required

        if has_free:
            self.pages[page_size] += pages_count
            self.memory -= page_size * pages_count

        return has_free

    def report(self):
        return [{'count': count,
                 'numa_id': self.id,
                 'size': self._format_size(size)}
                for size, count in self.pages.items()]

    def _format_size(self, size_in_bytes):
        return str(size_in_bytes // 1024)


class Component(object):
    def __init__(self, value):
        self.pages = {int(key) * 1024: int(value)
                      for key, value in value.items()}

    def allocate(self, size, limit):
        assert self.pages[size] >= limit
        self.pages[size] -= limit

    def is_done(self):
        return sum(self.pages.values()) == 0


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

    _allocate(numa_nodes, all_comps)
    _allocate(numa_nodes, any_comps)

    return sum([n.report() for n in numa_nodes], [])


def _allocate(numa_nodes, components):
    numa_nodes = iter(numa_nodes)
    components = iter(components)

    nnode = next(numa_nodes)
    comp = next(components)

    while True:
        allocated = nnode.allocate(comp)

        if comp.is_done():
            try:
                comp = next(comp)
            except StopIteration:
                break

        if not allocated:
            try:
                nnode = next(numa_nodes)
            except StopIteration:
                raise ValueError('Not enough memory for components')
