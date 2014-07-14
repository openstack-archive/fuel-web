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
import zlib


class Target(object):
    __metaclass__ = abc.ABCMeta

    def __iter__(self):
        return self

    def next(self):
        raise StopIteration()

    def target(self, filename='/dev/null'):
        with open(filename, 'wb') as f:
            for chunk in self:
                f.write(chunk)
            f.flush()


class LocalFile(Target):
    def __init__(self, filename):
        self.filename = str(filename)
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
        return iter(requests.get(self.url, stream=True).iter_content(1048576))


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
                proc.target(next_proc)
                return LocalFile(next_proc)
            # if next_proc is not a string we return new instance
            # initialized with the previous one
            else:
                return next_proc(proc)
        return reduce(jump, self.processors)
