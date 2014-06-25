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
from __future__ import print_function

from itertools import ifilter
from itertools import imap
import json
import os

import yaml


class Serializer(object):
    """Serializer class - contains all logic responsible for
    printing to stdout, reading and writing files to file system.
    """
    serializers = {
        "json": {
            "w": lambda d: json.dumps(d, indent=4),
            "r": lambda d: json.loads(d)
        },
        "yaml": {
            "w": lambda d: yaml.safe_dump(d, default_flow_style=False),
            "r": lambda d: yaml.load(d)
        }
    }

    format_flags = False
    default_format = "yaml"
    format = default_format

    def __init__(self, **kwargs):
        for f in self.serializers:
            if kwargs.get(f, False):
                self.format = f
                self.format_flags = True
                break

    @property
    def serializer(self):
        return self.serializers[self.format]

    @classmethod
    def from_params(cls, params):
        kwargs = dict((key, getattr(params, key)) for key in cls.serializers)
        return cls(**kwargs)

    def print_formatted(self, data):
            print(self.serializer["w"](data))

    def print_to_output(self, formatted_data, arg, print_method=print):
        if self.format_flags:
            self.print_formatted(formatted_data)
        else:
            if isinstance(arg, unicode):
                arg = arg.encode('utf-8')
            print_method(arg)

    def prepare_path(self, path):
        return "{0}.{1}".format(
            path, self.format
        )

    def write_to_file(self, path, data):
        full_path = self.prepare_path(path)
        with open(full_path, "w+") as file_to_write:
            file_to_write.write(self.serializer["w"](data))
        return full_path

    def read_from_file(self, path):
        full_path = self.prepare_path(path)
        with open(full_path, "r") as file_to_read:
            return self.serializer["r"](file_to_read.read())


def listdir_without_extensions(dir_path):
    return ifilter(
        lambda f: f != "",
        imap(
            lambda f: f.split(".")[0],
            os.listdir(dir_path)
        )
    )
