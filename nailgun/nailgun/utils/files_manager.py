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
from nailgun.logger import logger


class FilesManager(object):
    """Files Manager allows to load and save files with auto-serialization.

    All files loading and saving operations are recommended to be
    performed via FilesManager class.

    Also, it's recommended to work with FM using absolute paths to avoid
    relative paths mess.
    """
    _deserializers = {
        "json": json.loads,
        "yaml": yaml.safe_load,
        "txt": lambda v: v,
        "md": lambda v: v
    }

    _serializers = {
        "json": json.dumps,
        "yaml": yaml.safe_dump,
        "txt": lambda v: v,
        "md": lambda v: v
    }

    @staticmethod
    def _get_normalized_extension(path):
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

    @staticmethod
    def _merge_data_records(data_records):
        """Merge data records.

        Accepting lists and dict structures respecting order of records.

        If we are having at least one record with list as root we are extending
        this record by all other found lists and appending records with objects
        as root.

        If all records have object as root, fields will be overridden for every
        this records in given order.

        example 1:
            _merge_data_records([
                [{'field1': 1}],
                {'field2': 2},
                [{'field1': 3}],
            ])
        will return:
            [
                {'field1': 1},
                {'field2': 2},
                {'field1': 3}
            ]

        example 2:
            _merge_data_records([
                {'field1': 1},
                {'field2': 2},
                {'field1': 3},
            ])
        will return:
            {
                'field1': 3,
                'field2': 2
            }

        :param data_records: list of data records
        :type data_records: list[list|dict]

        :return: resulting data
        :rtype: list|dict|other objects
        """
        unmergable = []
        dicts_to_merge = []
        merged_list = []

        for data_record in data_records:
            if isinstance(data_record, dict):
                dicts_to_merge.append(data_record)
            elif isinstance(data_record, list):
                merged_list.extend(data_record)
            else:
                unmergable.append(data_record)

        if len(merged_list):  # we have list as root structure
            merged_list.extend(dicts_to_merge)
            merged_list.extend(unmergable)
            return merged_list
        elif len(dicts_to_merge):
            merged_dict = {}
            for dict_to_merge in dicts_to_merge:
                merged_dict.update(dict_to_merge)
            return merged_dict
        elif len(unmergable) == 1:
            return unmergable[0]
        elif len(unmergable) > 1:
            return unmergable

    @property
    def supported_input_formats(self):
        return list(self._deserializers)

    @property
    def supported_output_formats(self):
        return list(self._serializers)

    def load(
            self,
            path_mask,
            skip_unknown_files=False,
            skip_unredable_files=False,
            *args,
            **kwargs
    ):
        """Load file from path mask or direct path.

        :param path_mask: path
        :type path_mask: str

        :param skip_unknown_files: not stop on deserialization errors
                                   default=False
        :type skip_unknown_files: bool

        :param skip_unredable_files: not stop on file reading errors
                                   default=False
        :type skip_unredable_files: bool

        :raises: InvalidFileFormat
        :raises: NoPluginFileFound
        :raises: TypeError
        :raises: yaml.YAMLError

        :return: data
        :rtype: list|dict
        """
        paths = self._get_files_by_mask(
            path_mask, self.supported_input_formats)
        if not paths:
            raise errors.NoPluginFileFound(
                u"Can't find file. "
                u"Ensure that file is on its place and have one of "
                u"the following data files formats: {}.".format(
                    u", ".join(self.supported_input_formats)
                )
            )
        data_records = []
        for path in paths:
            extension = self._get_normalized_extension(path)
            deserializer = self._deserializers.get(extension)

            if deserializer is not None:
                try:
                    with open(path, 'r') as content_file:
                        raw_content = content_file.read()
                        data_records.append(
                            deserializer(raw_content, *args, **kwargs)
                        )
                except IOError as e:
                    if skip_unredable_files:
                        logger.error(e.message)
                    else:
                        raise e
            else:
                e = errors.InvalidFileFormat(
                    path, self.supported_input_formats)
                if skip_unknown_files:
                    logger.error(e.message)
                else:
                    raise e

        return self._merge_data_records(data_records)

    def save(self, path, mode='w', *args, **kwargs):
        """Save data to given file path applying serializer.

        :param path: full path with extension that will define serialization
                     format.
        :type path: str

        :param mode: file write mode
        :type mode: str|basestring

        :raises: InvalidFileFormat
        :raises: TypeError
        :raises: yaml.YAMLError

        :return: data
        :rtype: list|dict
        """
        extension = self._get_normalized_extension(path)
        serializer = self._serializers.get(extension)
        if serializer is not None:
            serialized_data = serializer(path, *args, **kwargs)
            with open(path, mode) as content_file:
                content_file.write(serialized_data)
        else:
            raise errors.InvalidFileFormat(
                path, self.supported_output_formats)
