# -*- coding: utf-8 -*-
#
#    Copyright 2016 Mirantis, Inc.
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

import glob
import json
import os

import yaml

from nailgun import errors


def deserializer_json(raw_data, *args, **kwargs):
    """Load JSON data from file object.

    :param raw_data: raw data
    :type raw_data: basestring

    :return: data
    :rtype: list|dict
    """
    return json.load(raw_data, *args, **kwargs)


def deserializer_yaml(raw_data, loader=yaml.Loader, *args, **kwargs):
    """Load YAML data from file object.

    :param raw_data: raw data
    :type raw_data: basestring
    :param loader: YAML-specific loader
    :type loader: yaml.Loader

    :return: data
    :rtype: list|dict
    """
    return yaml.safe_load(raw_data, Loader=loader)


def deserializer_plaintext(raw_data, *args, **kwargs):
    """Load plaintext data from file object.

    Not doing anything except passing data throug.

    :param raw_data: text
    :type raw_data: basestring

    :return: data
    :rtype: list|dict
    """
    return raw_data


def serializer_json(data, *args, **kwargs):
    """Load JSON data from file object.

    :param data: data
    :type data: dict|list

    :return: raw data
    :rtype: basestring
    """
    return json.dumps(data, *args, **kwargs)


def serializer_yaml(data, dumper=yaml.SafeDumper, *args, **kwargs):
    """Load YAML data from file object.

    :param data: data
    :type data: dict|list
    :param dumper: YAML-specific dumper
    :type dumper: yaml.Dumper

    :return: data
    :rtype: basestring
    """
    return yaml.dump(data, Dumper=dumper, **kwargs)


def serializer_plaintext(data, *args, **kwargs):
    """Serialize plaintext to string.

    Not doing anything except passing data throug.

    :param data: data
    :type data: basestring

    :return: data
    :rtype: basestring
    """
    return data


DESERIALIZERS = {
    "json": deserializer_json,
    "yaml": deserializer_yaml,
    "txt": deserializer_plaintext
}

SERIALIZERS = {
    "json": serializer_json,
    "yaml": serializer_yaml,
    "txt": serializer_plaintext
}


class FilesManager(object):
    """Files Manager is responsive for data serialization and files operations.

    All files loading and saving operations are recommended to be
    performed via FilesManager class.

    Also, it's recommended to work with FM using absolute paths to avoid
    relative paths mess.
    """

    def _get_normalized_extension(self, path):
        """Get normalized file extension.

        :param path: path
        :type path: str|basestring

        :return: lowercased extension without dot
        :rtype: str|basestring
        """
        extension = os.path.splitext(path)[1].lower()
        if extension:
            if extension[0] == '.':
                extension = extension[1:]
        return extension

    def _get_files_by_mask(self, path_mask, allowed_formats=None):
        """Find all files of allowed format in path.

        :param path_mask: path mask like ./my-file.*
        :type path_mask: str|basestring

        :param allowed_formats: available file formats
                                allow all if not defined
        :type allowed_formats: iterable|None

        :return: list of sorted files paths
        :rtype: list
        """

        paths = []
        for path in glob.glob(path_mask):
            extension = self._get_normalized_extension(path)
            if not allowed_formats or extension in allowed_formats:
                paths.append(path)

        if paths:
            return sorted(paths)
        raise errors.NoPluginFileFound(
            u"Can't find file by mask '{}'. "
            u"Ensure that file is on its place and have one of the following "
            u"data files formats: {}.".format(
                path_mask,
                u", ".join(list(allowed_formats))
            )
        )

    def _merge_data_records(self, data_records):
        """Merge data records.

        Accepting lists and dict structures respecting order of records.

        :param data_records: list of data records
        :type data_records: list[list|dict]

        :return: resulting data
        :rtype: list|dict
        """
        dicts_to_merge = []
        merged_list = []
        for data_record in data_records:
            if isinstance(data_record, dict):
                dicts_to_merge.append(data_record)
            elif isinstance(data_record, list):
                merged_list.extend(data_record)
        if len(merged_list):  # we have list as root structure
            merged_list.extend(dicts_to_merge)
            return merged_list
        elif len(dicts_to_merge):
            merged_dict = {}
            for dict_to_merge in dicts_to_merge:
                merged_dict.update(dict_to_merge)
            return merged_dict

    def load(self, path_mask, skip_unknown_files=False, *args, **kwargs):
        """Load file from path mask or direct path.

        :param path_mask: path
        :type path_mask: str

        :param skip_unknown_files: not stop on deserialization errors
        :type skip_unknown_files: bool

        :return: data
        :rtype: list|dict
        """
        paths = self._get_files_by_mask(path_mask, list(DESERIALIZERS))
        data_records = []
        for path in paths:
            extension = self._get_normalized_extension(path)
            deserializer = DESERIALIZERS.get(extension)

            if deserializer is not None:
                with open(path, 'r') as content_file:
                    raw_content = content_file.read()
                    data_records.append(
                        deserializer(raw_content, *args, **kwargs)
                    )
            elif not skip_unknown_files:
                raise IOError(
                    path,
                    list(DESERIALIZERS)
                )
        return self._merge_data_records(data_records)

    def save(self, path, *args, **kwargs):
        """Save data to path applying serializer.

        :param path: full path with extension that will define serialization
                     format.
        :type path: str

        :return: data
        :rtype: list|dict
        """
        extension = self._get_normalized_extension(path)
        serializer = SERIALIZERS.get(extension)

        if serializer is not None:
            return serializer(path, *args, **kwargs)
        else:
            raise errors.InvalidFileFormat(path, list(SERIALIZERS))
