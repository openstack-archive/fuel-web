import inspect
from nailgun.settings import settings

objs = __import__(settings.OBJECTS_IMPL, fromlist=['*'])
for name, value in inspect.getmembers(objs):
    if inspect.isclass(value) or inspect.ismodule(value):
        globals()[name] = value
