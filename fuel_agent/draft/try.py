
import os
import jinja2


class A(object):
    pass

class B(object):
    pass

class C(object):
    pass

env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.getcwd()))
template = env.get_template('try.template')

parent = A()

config1 = B()
config1.attr1 = 'config1val1'
config1.attr2 = 'config1val2'
config2 = C()
config2.attr1 = 'config2val1'
config2.attr2 = 'config2val2'

parent.config1 = config1
parent.config2 = config2

# config1 = {'attr1': 'config1val1', 'attr2': 'config1val2'}
# config2 = {'attr1': 'config2val1', 'attr2': 'config2val2'}

output = template.render({'parent': parent})
print output



