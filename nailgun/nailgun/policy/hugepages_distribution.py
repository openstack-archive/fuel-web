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

        for page_size, pages_required in component.pages():
            # calculate pages count that we can allocate with this
            # size on this numa node
            available = self.free_memory // page_size

            if available == 0:
                continue

            limit = min(pages_required, available)
            allocated_pages = component.allocate(page_size, limit)

            self.pages[page_size] += allocated_pages
            self.free_memory -= page_size * allocated_pages
            allocated |= bool(allocated_pages)

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
        """Allocate pages_count of page_size for this component.

        Return count of pages that was allocated. If component is_done
        than return 0

        """
        pages = self._pages

        if page_size not in pages:
            return 0

        available = pages[page_size]
        limit = min(available, pages_count)
        pages[page_size] -= limit

        if pages[page_size] == 0:
            pages.pop(page_size)

        return limit

    def pages(self):
        return self._pages.items()

    def is_done(self):
        return self._pages == {}


def distribute_hugepages(numa_topology, components):
    all_comps = [Component(comp) for comp in components['all']]
    any_comps = [Component(comp) for comp in components['any']]

    numa_nodes = [NumaNode(n['id'], n['memory'])
                  for n in numa_topology['numa_nodes']]

    _allocate_all(numa_nodes, all_comps)
    _allocate_any(numa_nodes, any_comps)

    return sum([n.report() for n in numa_nodes], [])


def _allocate_all(numa_nodes, components):
    """Allocate every component on all numa nodes."""
    for component in components:
        for nnode in numa_nodes:
            comp = copy.deepcopy(component)
            allocated = nnode.allocate(comp)
            assert allocated and comp.is_done()


def _allocate_any(numa_nodes, components):
    """Allocate every component on some numa nodes.

    For now we don't make a distinction between components so just
    merge them in big one and try to allocate on nodes.

    """
    comp = _merge_components(components)

    for nnode in numa_nodes:
        nnode.allocate(comp)
        if comp.is_done():
            break
    else:
        # if we check all nodes with same component and not found
        # free memory for allocation then raise error
        raise ValueError('Not enough memory for components')


def _merge_components(components):
    res = collections.defaultdict(int)
    for comp in components:
        for size, count in comp.pages():
            res[size] += count

    return Component({size // 1024: count for size, count in res.items()})
