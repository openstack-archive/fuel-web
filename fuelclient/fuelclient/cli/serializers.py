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

import os
import json
import yaml


class Serializer:

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

    format = None
    format_flags = False
    default_format = "yaml"

    def __init__(self, params=None):
        if params is not None:
            for f in self.serializers.keys():
                if getattr(params, f):
                    self.format = f
                    self.format_flags = True
                    break
            if not self.format_flags:
                self.format = self.default_format
        else:
            self.format = self.default_format
        self.serializer = self.serializers[self.format]

    def print_formatted(self, data):
            print(self.serializer["w"](data))

    def print_to_output(self, formatted_data, arg, print_method=print):
        if self.format_flags:
            self.print_formatted(formatted_data)
        else:
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
            return self.serializer["r"](file_to_read.read()), full_path


def folder_or_one_up(dir_path):
    if not os.path.exists(dir_path):
        path_to_folder = dir_path.split(os.sep)
        one_folder_up = path_to_folder[:-2] + path_to_folder[-2:-1]
        dir_path = os.sep.join(one_folder_up)
    return dir_path


def listdir_without_extensions(dir_path):
    return filter(
        lambda f: f != "",
        map(
            lambda f: f.split(".")[0],
            os.listdir(dir_path)
        )
    )
