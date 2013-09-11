import operator
import os
import sys

from .constants import *
from .module import Module
from .moduleset import ModuleSet

import ethtool


# set up logging
import logging
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger('fuelmenu.loader')

class Loader:

    def __init__(self):
        self.modlist = []

    def load_modules(self, module_dir):
        if not module_dir in sys.path:
            sys.path.append(module_dir)

        modules = [os.path.splitext(f)[0] for f in os.listdir(module_dir)
                   if f.endswith('.py')]

        for module in modules:
            log.info('loading module %s', module)
            try:
                imported = process(module)
            except ImportError as e:
                log.error('module could not be imported: %s', e)
                continue
            # add the module to the list
            self.modlist.append(module)
        # sort modules
        self.modlist.sort(key=operator.attrgetter('priority'))
        return self.modlist


