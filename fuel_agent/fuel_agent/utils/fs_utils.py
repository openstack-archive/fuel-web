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
    cmd_line.append(cmd_name)
    for opt in (fs_options, fs_label):
        cmd_line.extend([s for s in opt.split(' ') if s])
    cmd_line.append(dev)
    utils.execute(*cmd_line)


def extend_fs(fs_type, fs_dev):
    if fs_type.startswith('ext3') or fs_type.startswith('ext4'):
        # ext3,4 file system can be mounted
        # must be checked with e2fsck -f
        utils.execute('e2fsck', ' -f', fs_dev, check_exit_code=[0])
        utils.execute('resize2fs', fs_dev, check_exit_code=[0])
    elif fs_type.startswith('xfs'):
        # xfs file system must be mounted
        utils.execute('xfs_growfs', fs_dev, check_exit_code=[0])
    else:
        raise Exception('Unsupported file system type')


def mount_fs(fs_type, fs_dev, fs_mount):
    utils.execute('mount', '-t', fs_type, fs_dev, fs_mount,
                  check_exit_code=[0])

def mount_bind(chroot, path, path2=None):
    if not path2:
        path2 = path
    utils.execute('mount', '--bind', path, chroot + path2,
                  check_exit_code=[0])

def umount_fs(fs_mount):
    utils.execute('umount', fs_mount, check_exit_code=[0])
