import yaml
import collections
def construct_ordered_mapping(self, node, deep=False):
    if not isinstance(node, yaml.MappingNode):
        raise ConstructorError(None, None,
                "expected a mapping node, but found %s" % node.id,
                node.start_mark)
    mapping = collections.OrderedDict()
    for key_node, value_node in node.value:
        key = self.construct_object(key_node, deep=deep)
        if not isinstance(key, collections.Hashable):
            raise ConstructorError("while constructing a mapping", node.start_mark,
                    "found unhashable key", key_node.start_mark)
        value = self.construct_object(value_node, deep=deep)
        mapping[key] = value
    return mapping
yaml.constructor.BaseConstructor.construct_mapping = construct_ordered_mapping
def construct_yaml_map_with_ordered_dict(self, node):
    data = collections.OrderedDict()
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
        if not (isinstance(node_value, yaml.ScalarNode) and not node_value.style):
            best_style = False
        value.append((node_key, node_value))
    if flow_style is None:
        if self.default_flow_style is not None:
            node.flow_style = self.default_flow_style
        else:
            node.flow_style = best_style
    return node
yaml.representer.BaseRepresenter.represent_mapping = represent_ordered_mapping
yaml.representer.Representer.add_representer(collections.OrderedDict,
yaml.representer.SafeRepresenter.represent_dict)


class Settings():
  def __init__(self):
     pass
  def read(self, yamlfile):
     infile = file('astute.yaml', 'r')
     settings = yaml.load(infile)
     return settings

  def write(self, newvalues, tree=None, defaultsfile='config.yaml', outfn='mysettings.yaml'):
     infile = file(defaultsfile, 'r')
     outfile = file(outfn, 'w')
     settings = yaml.load(infile)
     #settings.update(newvalues)
     yaml.dump(settings, outfile, default_flow_style=False)
     return True







#import yaml
#import yaml.constructor
#
#try:
#    # included in standard lib from Python 2.7
#    from collections import OrderedDict
#except ImportError:
#    # try importing the backported drop-in replacement
#    # it's available on PyPI
#    from ordereddict import OrderedDict
#
#class OrderedDictYAMLLoader(yaml.Loader):
#    """
#    A YAML loader that loads mappings into ordered dictionaries.
#    """
#
#    def __init__(self, *args, **kwargs):
#        yaml.Loader.__init__(self, *args, **kwargs)
#
#        self.add_constructor(u'tag:yaml.org,2002:map', type(self).construct_yaml_map)
#        self.add_constructor(u'tag:yaml.org,2002:omap', type(self).construct_yaml_map)
#
#    def construct_yaml_map(self, node):
#        data = OrderedDict()
#        yield data
#        value = self.construct_mapping(node)
#        data.update(value)
#
#    def construct_mapping(self, node, deep=False):
#        if isinstance(node, yaml.MappingNode):
#            self.flatten_mapping(node)
#        else:
#            raise yaml.constructor.ConstructorError(None, None,
#                'expected a mapping node, but found %s' % node.id, node.start_mark)
#
#        mapping = OrderedDict()
#        for key_node, value_node in node.value:
#            key = self.construct_object(key_node, deep=deep)
#            try:
#                hash(key)
#            except TypeError, exc:
#                raise yaml.constructor.ConstructorError('while constructing a mapping',
#                    node.start_mark, 'found unacceptable key (%s)' % exc, key_node.start_mark)
#            value = self.construct_object(value_node, deep=deep)
#            mapping[key] = value
#        return mapping

if __name__ == '__main__':
    import textwrap

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
    infile = file('config.yaml', 'r')
    data = yaml.load(infile)
    #data = yaml.load(infile, OrderedDictYAMLLoader)
    #data = yaml.load(textwrap.dedent(sample), OrderedDictYAMLLoader)
    outfile = file("testout", 'w')
    yaml.dump(data, outfile, default_flow_style=False)


    #assert type(data) is OrderedDict
    print data.items()


