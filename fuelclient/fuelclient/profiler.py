# -*- coding: utf-8 -*-
#
#    Copyright 2014 Mirantis, Inc.
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

import cProfile
import os
from pstats import Stats
import time

from fuelclient.cli import error
from fuelclient import fuelclient_settings


def profiling_enabled():
    settings = fuelclient_settings.get_settings()
    return bool(settings.PERFORMANCE_PROFILING_TESTS)


class Profiler(object):
    """Runs profiler and saves results."""

    def __init__(self, method='', handler_name=''):
        self.method = method
        self.handler_name = handler_name
        settings = fuelclient_settings.get_settings()
        self.paths = settings.PERF_TESTS_PATHS

        if not os.path.exists(self.paths['last_performance_test']):
            os.makedirs(self.paths['last_performance_test'])

        self.profiler = cProfile.Profile()
        self.profiler.enable()
        self.start = time.time()

    def save_data(self):
        try:
            import gprof2dot
            import pyprof2calltree
        except ImportError:
            msg = ('Unable to start profiling.\n Please either '
                   'disable performance profiling in settings.yaml or '
                   'install all modules listed in test-requirements.txt.')
            raise error.ProfilingError(msg)

        self.profiler.disable()
        elapsed = time.time() - self.start
        pref_filename = os.path.join(
            self.paths['last_performance_test'],
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
