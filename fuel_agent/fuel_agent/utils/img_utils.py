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

from fuel_agent.utils import utils


def deploy(filename, target_device):
    utils.execute('dd', 'if=%s' % filename, 'of=%s' % target_device, 'bs=1M',
                  check_exit_code=[0])


def download(uri, filename):
    if uri.startswith('http://'):
        utils.execute('wget', '-O%s' % filename, uri, check_exit_code=[0])
    elif uri.startswith('file://'):
        orig_filename = uri.replace('file://', '')
        if orig_filename != filename:
            utils.execute('cp', orig_filename, filename, check_exit_code=[0])


def process(image_container, orig_filename, filename):
    pass
