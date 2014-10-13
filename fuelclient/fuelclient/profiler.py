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

import os
import time

import cProfile
import gprof2dot
from pstats import Stats
import pyprof2calltree

from fuelclient import consts


class Profiler(object):
    """Run profiler and save profile
    """
    def __init__(self, method='', handler_name=''):
        self.method = method
        self.handler_name = handler_name
        if not os.path.exists(consts.LOAD_TESTS_PATHS.last_load_test):
            os.makedirs(consts.LOAD_TESTS_PATHS.last_load_test)
        self.profiler = cProfile.Profile()
        self.profiler.enable()
        self.start = time.time()

    def save_data(self):
        self.profiler.disable()
        elapsed = time.time() - self.start
        pref_filename = os.path.join(
            consts.LOAD_TESTS_PATHS.last_load_test,
            '{method:s}.{handler_name:s}.{elapsed_time:.0f}ms.{t_time}.'.
            format(
                method=self.method,
                handler_name=self.handler_name or 'root',
                elapsed_time=elapsed * 1000.0,
                t_time=time.time()))
        tree_file = pref_filename + 'prof'
        stats_file = pref_filename + 'txt'
        callgraph_file = pref_filename + 'dot'

        # write pstats
        with file(stats_file, 'w') as file_o:
            stats = Stats(self.profiler, stream=file_o)
            stats.sort_stats('time', 'cumulative').print_stats()

        # write callgraph in dot format
        parser = gprof2dot.PstatsParser(self.profiler)

        def get_function_name((filename, line, name)):
            module = os.path.splitext(filename)[0]
            module_pieces = module.split(os.path.sep)
            return "{module:s}:{line:d}:{name:s}".format(
                module="/".join(module_pieces[-4:]),
                line=line,
                name=name)

        parser.get_function_name = get_function_name
        gprof = parser.parse()

        with open(callgraph_file, 'w') as file_o:
            dot = gprof2dot.DotWriter(file_o)
            theme = gprof2dot.TEMPERATURE_COLORMAP
            dot.graph(gprof, theme)

        # write calltree
        call_tree = pyprof2calltree.CalltreeConverter(stats)
        with file(tree_file, 'wb') as file_o:
            call_tree.output(file_o)
