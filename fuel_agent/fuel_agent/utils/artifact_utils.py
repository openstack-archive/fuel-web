# Copyright 2014 Mirantis, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import abc
import requests
import tarfile
import tempfile
import zlib

from fuel_agent.openstack.common import log as logging

LOG = logging.getLogger(__name__)


class Target(object):
    __metaclass__ = abc.ABCMeta

    def __iter__(self):
        return self

    def next(self):
        raise StopIteration()

    def target(self, filename='/dev/null'):
        LOG.debug('Opening file: %s for write' % filename)
        with open(filename, 'wb') as f:
            count = 0
            for chunk in self:
                LOG.debug('Next chunk: %s' % count)
                f.write(chunk)
                count += 1
            LOG.debug('Flushing file: %s' % filename)
            f.flush()
        LOG.debug('File is written: %s' % filename)


class LocalFile(Target):
    def __init__(self, filename):
        if filename.startswith('file://'):
            self.filename = filename[7:]
        else:
            self.filename = filename
        self.fileobj = None

    def next(self):
        if not self.fileobj:
            self.fileobj = open(self.filename, 'rb')
        buffer = self.fileobj.read(1048576)
        if buffer:
            return buffer
        else:
            self.fileobj.close()
            raise StopIteration()


class HttpUrl(Target):
    def __init__(self, url):
        self.url = str(url)

    def __iter__(self):
        response = requests.get(self.url, stream=True)
        if response.status_code != 200:
            raise Exception('Can not get %s' % self.url)
        return iter(response.iter_content(1048576))


class GunzipStream(Target):
    def __init__(self, stream):
        self.stream = iter(stream)
        #NOTE(agordeev): toggle automatic header detection on
        self.decompressor = zlib.decompressobj(zlib.MAX_WBITS | 32)

    def next(self):
        try:
            return self.decompressor.decompress(self.stream.next())
        except StopIteration:
            raise


class ForwardFileStream(Target):
    def __init__(self, stream):
        self.stream = iter(stream)
        self.position = 0
        self.chunk = ''
        self.closed = False

    def next(self):
        buffer = self.read()
        if buffer:
            return buffer
        else:
            raise StopIteration()

    def close(self):
        self.closed = True

    def tell(self):
        if self.closed:
            raise ValueError('I/O operation on closed file')
        return self.position

    def seek(self, position):
        if self.closed:
            raise ValueError('I/O operation on closed file')

        if position < self.position:
            raise ValueError('Backward seek operation is impossible')
        elif position < self.position + len(self.chunk):
            self.chunk = self.chunk[(position - self.position):]
            self.position = position
        else:
            try:
                current = self.position + len(self.chunk)
                while True:
                    chunk = self.stream.next()
                    if current + len(chunk) >= position:
                        self.chunk = chunk[(position - current):]
                        self.position = position
                        break
                    current += len(chunk)
            except StopIteration:
                self.chunk = None
                self.position = position

    def read(self, length=1048576):
        # NOTE(kozhukalov): default lenght = 1048576 is not usual behaviour,
        # but that is ok for our use case.
        if self.closed:
            raise ValueError('I/O operation on closed file')
        if self.chunk is None:
            return None
        try:
            while len(self.chunk) < length:
                self.chunk += self.stream.next()
            result = self.chunk[:length]
            self.chunk = self.chunk[length:]
        except StopIteration:
            result = self.chunk
            self.chunk = None
        self.position += len(result)
        return result


class TarStream(Target):
    def __init__(self, stream):
        self.stream = iter(stream)
        self.tarobj = None

    def target(self, filename=None):
        if not self.tarobj:
            self.tarobj = tarfile.open(
                fileobj=ForwardFileStream(self.stream), mode='r:')
        self.tarobj.extractall(path=(filename or tempfile.gettempdir()))


class Chain(object):
    def __init__(self):
        self.processors = []

    def append(self, processor):
        self.processors.append(processor)

    def process(self):
        def jump(proc, next_proc):
            # if next_proc is just a string we assume it is a filename
            # and we save stream into a file
            if isinstance(next_proc, (str, unicode)):
                LOG.debug('Processor target: %s' % next_proc)
                proc.target(next_proc)
                return LocalFile(next_proc)
            # if next_proc is not a string we return new instance
            # initialized with the previous one
            else:
                return next_proc(proc)
        return reduce(jump, self.processors)
