import functools

class A:
    def meth1(self, a, b):
        print 'meth1: a=%s b=%s' % (a, b)

    def meth2(self):
        return functools.partial(self.meth1, a=1)

a = A()
b = a.meth2()
b(b=3)


