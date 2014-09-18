
TYPES = {}


class MetaObject(type):
    # def __new__(meta, name, bases, dct):
    #     TYPES[dct['__name__']] = name

    def __init__(self, name, bases, dct):
        TYPES[dct['__name__']] = self
        print 'name: %s' % name
        print 'bases: %s' % bases
        print 'dct: %s' % dct


class Vm(object):
    __metaclass__ = MetaObject
    __name__ = 'vm'


    def __init__(self):
        pass


class Net(object):
    __metaclass__ = MetaObject
    __name__ = 'net'

    def __init__(self):
        pass

print TYPES