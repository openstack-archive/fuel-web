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

from contextlib import contextmanager
from functools import partial
import logging
import signal


log = logging.getLogger(__name__)


class TimeoutException(KeyboardInterrupt):
    """Exception should be raised if timeout is exceeded."""


def timeout_handler(timeout, signum, frame):
    raise TimeoutException("Timeout {0} seconds exceeded".format(timeout))


@contextmanager
def signal_timeout(timeout, raise_exc=True):
    """Timeout handling using signals

    :param timeout: timeout in seconds, integer
    :param raise_exc: bool to control suppressing of exception
    """
    handler = partial(timeout_handler, timeout)

    signal.signal(signal.SIGALRM, handler)
    signal.alarm(timeout)

    try:
        yield
    except TimeoutException as exc:
        if raise_exc:
            raise
        else:
            log.warning(str(exc))
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, signal.SIG_DFL)
