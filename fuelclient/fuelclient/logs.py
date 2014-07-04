# -*- coding: utf-8 -*-

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

import logging


class NullHandler(logging.Handler):
    """This handler does nothing. It's intended to be used to avoid the
    "No handlers could be found for logger XXX" one-off warning. This
    important for library code, which may contain code to log events.
    of the library does not configure logging, the one-off warning mig
    produced; to avoid this, the library developer simply needs to ins
    a NullHandler and add it to the top-level logger of the library mo
    package.

    Taken from Python 2.7
    """
    def handle(self, record):
        pass

    def emit(self, record):
        pass

    def createLock(self):
        self.lock = None
