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

from collections import namedtuple
import fnmatch
import os
import subprocess


Status = namedtuple('Status', ['name', 'code'])


def key_value_enum(enums):
    enums = dict([(k, Status(k, v)) for k, v in enums.iteritems()])
    return type('Enum', (), enums)


STATUS = key_value_enum({'running': 1,
                         'end': 0,
                         'error': 3,
                         'notfound': 4,
                         'failed': 2})


def find_all_tasks(config):
    for root, dirnames, filenames in os.walk(config['library_dir']):
        for filename in fnmatch.filter(filenames, config['task_file']):
            yield os.path.dirname(os.path.join(root, filename))


def ensure_dir_created(path):
    if not os.path.exists(path):
        os.makedirs(path)


def execute(cmd):
    command = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    stdout, stderr = command.communicate()
    return command.returncode, stdout, stderr
