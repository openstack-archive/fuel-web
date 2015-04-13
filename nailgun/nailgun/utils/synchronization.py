# -*- coding: utf-8 -*-

#    Copyright 2015 Mirantis, Inc.
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

import fcntl
import os
import time


def barrier_by_const(barrier_const):
    """Wait on a barrier based on provided config."""
    b = Barrier(barrier_const.group, barrier_const.limit)
    b.wait()


class Barrier:
    def __init__(self, group, number, poll_wait=0.5):
        self.limit = number
        self.poll_wait = poll_wait
        self.handle_name = '/tmp/barrier-{0}'.format(group)
        self.handle = os.fdopen(
            os.open(self.handle_name, os.O_RDWR | os.O_CREAT), 'r+')

    def wait(self):
        self._increment_barrier_state()

        count = 0
        while count < self.limit:
            self._aquire()
            count = int(self._get_barrier_state())
            self._release()
            time.sleep(self.poll_wait)

    def _increment_barrier_state(self):
        self._aquire()
        content = self._get_barrier_state()
        if len(content) == 0:
            content = '0'
        current_state = int(content) + 1
        self._write_barrier_state(str(current_state))
        self._release()

    def _get_barrier_state(self):
        result = self.handle.read()
        self.handle.seek(0)
        return result

    def _write_barrier_state(self, state):
        self.handle.write(state)
        self.handle.seek(0)

    def _aquire(self):
        fcntl.flock(self.handle, fcntl.LOCK_EX)

    def _release(self):
        fcntl.flock(self.handle, fcntl.LOCK_UN)

    def __del__(self):
        self.handle.close()
        try:
            os.unlink(self.handle_name)
        except OSError:
            # file not found, already deleted by other process
            pass
