# Copyright 2013 Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import collections
try:
    from collections import OrderedDict
except Exception:
    # python 2.6 or earlier use backport
    from ordereddict import OrderedDict
import yaml


def construct_ordered_mapping(self, node, deep=False):
    if not isinstance(node, yaml.MappingNode):
        raise yaml.ConstructorError(None, None,
                                    "expected a mapping node, but found %s" %
                                    node.id, node.start_mark)
    mapping = OrderedDict()
    for key_node, value_node in node.value:
        key = self.construct_object(key_node, deep=deep)
        if not isinstance(key, collections.Hashable):
            raise yaml.ConstructorError(
                "while constructing a mapping", node.start_mark,
                "found unhashable key", key_node.start_mark)
        value = self.construct_object(value_node, deep=deep)
        mapping[key] = value
    return mapping
yaml.constructor.BaseConstructor.construct_mapping = construct_ordered_mapping


def construct_yaml_map_with_ordered_dict(self, node):
    data = OrderedDict()
    yield data
    value = self.construct_mapping(node)
    data.update(value)
yaml.constructor.Constructor.add_constructor(
    'tag:yaml.org,2002:map',
    construct_yaml_map_with_ordered_dict)


def represent_ordered_mapping(self, tag, mapping, flow_style=None):
    value = []
    node = yaml.MappingNode(tag, value, flow_style=flow_style)
    if self.alias_key is not None:
        self.represented_objects[self.alias_key] = node
    best_style = True
    if hasattr(mapping, 'items'):
        mapping = list(mapping.items())
    for item_key, item_value in mapping:
        node_key = self.represent_data(item_key)
        node_value = self.represent_data(item_value)
        if not (isinstance(node_key, yaml.ScalarNode) and not node_key.style):
            best_style = False
        if not (isinstance(node_value, yaml.ScalarNode)
                and not node_value.style):
            best_style = False
        value.append((node_key, node_value))
    if flow_style is None:
        if self.default_flow_style is not None:
            node.flow_style = self.default_flow_style
        else:
            node.flow_style = best_style
    return node
yaml.representer.BaseRepresenter.represent_mapping = represent_ordered_mapping
yaml.representer.Representer.add_representer(OrderedDict, yaml.representer.
                                             SafeRepresenter.represent_dict)


class Settings():
    def __init__(self):
        pass

    def read(self, yamlfile):
        try:
            infile = file(yamlfile, 'r')
            settings = yaml.load(infile)
            return settings
        except Exception:
            if yamlfile is not None:
                import logging
                logging.error("Unable to read YAML: %s" % yamlfile)
            return OrderedDict()

    def write(self, newvalues, tree=None, defaultsfile='settings.yaml',
              outfn='mysettings.yaml'):
        settings = self.read(defaultsfile)
        settings.update(self.read(outfn))
        settings.update(newvalues)
        outfile = file(outfn, 'w')
        yaml.dump(settings, outfile, default_flow_style=False)
        return True

if __name__ == '__main__':

    sample = """
    one:
        two: fish
        red: fish
        blue: fish
    two:
        a: yes
        b: no
        c: null
    """
    infile = file('settings.yaml', 'r')
    data = yaml.load(infile)
    #data = yaml.load(infile, OrderedDictYAMLLoader)
    #data = yaml.load(textwrap.dedent(sample), OrderedDictYAMLLoader)
    outfile = file("testout", 'w')
    yaml.dump(data, outfile, default_flow_style=False)

    #assert type(data) is OrderedDict
    print(data.items())
