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

import json
import hashlib
import os
try:
    from unittest.case import TestCase
except ImportError:
    # Runing unit-tests in production environment
    from unittest2.case import TestCase
import mock
import yaml

from fuel_agent import manager as fa_manager
from fuel_agent_ci.objects import environment
from fuel_agent.utils import utils

FUEL_AGENT_REPO_NAME = 'fuel_agent'
FUEL_AGENT_HTTP_NAME = 'http'
FUEL_AGENT_NET_NAME = 'net'
FUEL_AGENT_DHCP_NAME = 'dhcp'
FUEL_AGENT_CI_ENVIRONMENT_FILE = 'samples/ci_environment.yaml'
SSH_COMMAND_TIMEOUT = 150


class BaseFuelAgentCITest(TestCase):
    maxDiff = None

    def setUp(self):
        super(BaseFuelAgentCITest, self).setUp()
        with open(FUEL_AGENT_CI_ENVIRONMENT_FILE) as f:
            ENV_DATA = (yaml.load(f.read()))
        self.env = environment.Environment.new(**ENV_DATA)
        self.env.start()
        self.name = ENV_DATA['vm'][0]['name']
        repo_obj = self.env.item_by_name('repo', FUEL_AGENT_REPO_NAME)
        tgz_name = '%s.tar.gz' % repo_obj.name
        utils.execute('tar czf %s %s' % (tgz_name,
                                         os.path.join(self.env.envdir,
                                         repo_obj.path)))
        self.env.ssh_by_name(self.name).wait()
        self.env.ssh_by_name(self.name).put_file(
            tgz_name, os.path.join('/tmp', tgz_name))

        self.env.ssh_by_name(self.name).run(
            'tar xf %s' % os.path.join('/tmp', tgz_name),
            command_timeout=SSH_COMMAND_TIMEOUT)
        self.env.ssh_by_name(self.name).run(
            'pip install setuptools --upgrade',
            command_timeout=SSH_COMMAND_TIMEOUT)
        self.env.ssh_by_name(self.name).run(
            'cd /root/var/tmp/fuel_agent_ci/fuel_agent/fuel_agent; '
            'python setup.py install', command_timeout=SSH_COMMAND_TIMEOUT)
        self.http_obj = self.env.item_by_name('http', FUEL_AGENT_HTTP_NAME)
        self.dhcp_hosts = self.env.item_by_name('dhcp',
                                                FUEL_AGENT_DHCP_NAME).hosts
        self.net = self.env.item_by_name('net', FUEL_AGENT_NET_NAME)
        p_data = get_filled_provision_data(self.dhcp_hosts[0]['ip'],
                                           self.dhcp_hosts[0]['mac'],
                                           self.net.ip, self.http_obj.port)
        self.env.ssh_by_name(self.name).put_content(
            json.dumps(p_data), os.path.join('/tmp', 'provision.json'))
        self.mgr = fa_manager.Manager(p_data)

    def tearDown(self):
        super(BaseFuelAgentCITest, self).tearDown()
        self.env.stop()


def get_filled_provision_data(ip, mac, master_ip, port=8888, profile='ubuntu'):
    return {
        "profile": "ubuntu_1204_x86_64",
        "name_servers_search": "\"domain.tld\"",
        "uid": "1",
        "interfaces": {
            "eth0": {
                "ip_address": ip,
                "dns_name": "node-1.domain.tld",
                "netmask": "255.255.255.0",
                "static": "0",
                "mac_address": mac
            }
        },
        "interfaces_extra": {
            "eth0": {
                "onboot": "yes",
                "peerdns": "no"
            }
        },
        "power_type": "ssh",
        "power_user": "root",
        "kernel_options": {
            "udevrules": "%s_eth0" % mac,
            "netcfg/choose_interface": mac
        },
        "power_address": "10.20.0.253",
        "name_servers": "\"%s\"" % master_ip,
        "ks_meta": {
            "image_uri": "http://%s:%s/%s/%s.img.gz" % (master_ip, port,
                                                        profile, profile),
            "image_format": "raw",
            "image_container": "gzip",
            "timezone": "America/Los_Angeles",
            "master_ip": master_ip,
            "mco_enable": 1,
            "mco_vhost": "mcollective",
            "mco_pskey": "unset",
            "mco_user": "mcollective",
            "puppet_enable": 0,
            "fuel_version": "5.0.1",
            "install_log_2_syslog": 1,
            "mco_password": "marionette",
            "puppet_auto_setup": 1,
            "puppet_master": "fuel.domain.tld",
            "mco_auto_setup": 1,
            "auth_key": "fake_auth_key",
            "pm_data": {
                "kernel_params": "console=ttyS0,9600 console=tty0 rootdelay=90"
                                 " nomodeset",
                "ks_spaces": [
                    {
                        "name": "sda",
                        "extra": [
                            "disk/by-id/scsi-0QEMU_QEMU_HARDDISK_drive-scsi0-"
                            "0-0"
                        ],
                        "free_space": 10001,
                        "volumes": [
                            {
                                "type": "boot",
                                "size": 300
                            },
                            {
                                "mount": "/boot",
                                "size": 200,
                                "type": "raid",
                                "file_system": "ext2",
                                "name": "Boot"
                            },
                            {
                                "mount": "/tmp",
                                "size": 200,
                                "type": "partition",
                                "file_system": "ext2",
                                "partition_guid": "fake_guid",
                                "name": "TMP"
                            },
                            {
                                "type": "lvm_meta_pool",
                                "size": 0
                            },
                            {
                                "size": 3333,
                                "type": "pv",
                                "lvm_meta_size": 64,
                                "vg": "os"
                            },
                            {
                                "size": 800,
                                "type": "pv",
                                "lvm_meta_size": 64,
                                "vg": "image"
                            }
                        ],
                        "type": "disk",
                        "id": "sda",
                        "size": 10240
                    },
                    {
                        "name": "sdb",
                        "extra": [
                            "disk/by-id/scsi-0QEMU_QEMU_HARDDISK_drive-scsi0-"
                            "0-1"
                        ],
                        "free_space": 10001,
                        "volumes": [
                            {
                                "type": "boot",
                                "size": 300
                            },
                            {
                                "mount": "/boot",
                                "size": 200,
                                "type": "raid",
                                "file_system": "ext2",
                                "name": "Boot"
                            },
                            {
                                "type": "lvm_meta_pool",
                                "size": 64
                            },
                            {
                                "size": 0,
                                "type": "pv",
                                "lvm_meta_size": 0,
                                "vg": "os"
                            },
                            {
                                "size": 9071,
                                "type": "pv",
                                "lvm_meta_size": 64,
                                "vg": "image"
                            }
                        ],
                        "type": "disk",
                        "id": "sdb",
                        "size": 10240
                    },
                    {
                        "name": "sdc",
                        "extra": [
                            "disk/by-id/scsi-0QEMU_QEMU_HARDDISK_drive-scsi0-"
                            "0-2"
                        ],
                        "free_space": 10001,
                        "volumes": [
                            {
                                "type": "boot",
                                "size": 300
                            },
                            {
                                "mount": "/boot",
                                "size": 200,
                                "type": "raid",
                                "file_system": "ext2",
                                "name": "Boot"
                            },
                            {
                                "type": "lvm_meta_pool",
                                "size": 64
                            },
                            {
                                "size": 0,
                                "type": "pv",
                                "lvm_meta_size": 0,
                                "vg": "os"
                            },
                            {
                                "size": 4971,
                                "type": "pv",
                                "lvm_meta_size": 64,
                                "vg": "image"
                            }
                        ],
                        "type": "disk",
                        "id": "disk/by-path/pci-0000:00:04.0-scsi-0:0:2:0",
                        "size": 10240
                    },
                    {
                        "_allocate_size": "min",
                        "label": "Base System",
                        "min_size": 1937,
                        "volumes": [
                            {
                                "mount": "/",
                                "size": 1900,
                                "type": "lv",
                                "name": "root",
                                "file_system": "ext4"
                            },
                            {
                                "mount": "swap",
                                "size": 43,
                                "type": "lv",
                                "name": "swap",
                                "file_system": "swap"
                            }
                        ],
                        "type": "vg",
                        "id": "os"
                    },
                    {
                        "_allocate_size": "min",
                        "label": "Zero size volume",
                        "min_size": 0,
                        "volumes": [
                            {
                                "mount": "none",
                                "size": 0,
                                "type": "lv",
                                "name": "zero_size",
                                "file_system": "xfs"
                            }
                        ],
                        "type": "vg",
                        "id": "zero_size"
                    },
                    {
                        "_allocate_size": "all",
                        "label": "Image Storage",
                        "min_size": 1120,
                        "volumes": [
                            {
                                "mount": "/var/lib/glance",
                                "size": 1757,
                                "type": "lv",
                                "name": "glance",
                                "file_system": "xfs"
                            }
                        ],
                        "type": "vg",
                        "id": "image"
                    }
                ]
            },
            "mco_connector": "rabbitmq",
            "mco_host": master_ip
        },
        "name": "node-1",
        "hostname": "node-1.domain.tld",
        "slave_name": "node-1",
        "power_pass": "/root/.ssh/bootstrap.rsa",
        "netboot_enabled": "1"
    }
