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


def make_fs(fs_type, fs_options, fs_label, dev):
    # NOTE(agordeev): notice the different flag to force the fs creating
    #                ext* uses -F flag, xfs/mkswap uses -f flag.
    cmd_line = []
    cmd_name = 'mkswap'
    if fs_type is not 'swap':
        cmd_name = 'mkfs.%s' % fs_type
    cmd_name.append(cmd_name)
    for opt in (fs_options, fs_label):
        cmd_name.extend([s for s in opt.split(' ') if s])
    utils.execute(*cmd_line, dev)
