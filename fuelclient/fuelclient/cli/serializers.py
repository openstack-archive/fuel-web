#!/usr/bin/env python
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

import os


class Serializer:
    pass


class JsonSerializer(Serializer):
    format = "json"


class YamlSerializer(Serializer):
    format = "yaml"

serializers = (JsonSerializer, YamlSerializer)


def prepare_path(path):
    if JSON:
        serialisation_format = "json"
    elif YAML:
        serialisation_format = "yaml"
    else:
        serialisation_format = DEFAULT_SERIALIZER
    return "{0}.{1}".format(
        path, serialisation_format
    ), SERIALIZERS[serialisation_format]


def write_to_file(path, data):
    full_path, serializer = prepare_path(path)
    with open(full_path, "w+") as file_to_write:
        file_to_write.write(serializer["w"](data))
    return full_path


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


def read_from_file(path):
    full_path, serializer = prepare_path(path)
    with open(full_path, "r") as file_to_read:
        return serializer["r"](file_to_read.read()), full_path
