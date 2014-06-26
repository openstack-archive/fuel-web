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

import logging
import os
import re
import subprocess

import libvirt
import xmlbuilder

LOG = logging.getLogger(__name__)


def get_file_size(path):
    with open(path, 'rb') as file:
        current = file.tell()
        try:
            file.seek(0, 2)
            size = file.tell()
        finally:
            file.seek(current)
    return size


def get_qcow_size(path):
    p = subprocess.Popen(['qemu-img', 'info', path], stdout=subprocess.PIPE)
    output = p.communicate()[0]
    m = re.search(ur'.*?virtual size:.*?\((\d+) bytes\).*', output)
    return m.group(1)


class LibvirtDriver(object):

    def __init__(self, conn_str=None):
        self.conn = libvirt.open(conn_str or "qemu:///system")

    def net_define(self, name, uuid=None, bridge_name=None,
                   forward_mode=None, virtualport_type=None,
                   ip_address=None, ip_netmask=None,
                   dhcp=None, tftp_root=None):

        xml = xmlbuilder.XMLBuilder('network')
        xml.name(name)

        if uuid:
            xml.uuid(uuid)

        if bridge_name:
            xml.bridge(name=bridge_name)

        if forward_mode:
            xml.forward(mode=forward_mode)

        if virtualport_type:
            xml.virtualport(type=virtualport_type)

        if ip_address:
            with xml.ip(address=ip_address,
                        netmask=(ip_netmask or '255.255.255.0')):

                if tftp_root:
                    xml.tftp(root=tftp_root)

                if dhcp:
                    with xml.dhcp:
                        xml.range(start=dhcp['start'], end=dhcp['end'])
                        if dhcp.get('hosts'):
                            for host in dhcp['hosts']:
                                kwargs = {'mac': host['mac'], 'ip': host['ip']}
                                if host.get('name'):
                                    kwargs.update({'name': host['name']})
                                xml.host(**kwargs)
                        if dhcp.get('bootp'):
                            if dhcp['bootp'].get('server'):
                                xml.bootp(
                                    file=dhcp['bootp']['file'],
                                    server=dhcp['bootp']['server']
                                )
                            else:
                                xml.bootp(file=dhcp['bootp']['file'])

        net = self.conn.networkDefineXML(str(xml))
        return net.UUIDString()

    def net_start(self, uuid):
        net = self.conn.networkLookupByUUIDString(uuid)
        net.create()

    def net_destroy(self, uuid):
        net = self.conn.networkLookupByUUIDString(uuid)
        net.destroy()

    def net_undefine(self, uuid):
        net = self.conn.networkLookupByUUIDString(uuid)
        net.undefine()

    def net_uuid_by_name(self, name):
        net = self.conn.networkLookupByName(name)
        return net.UUIDString()

    def net_list(self):
        return self.conn.listDefinedNetworks() + self.conn.listNetworks()

    def net_list_active(self):
        return self.conn.listNetworks()

    def net_list_notactive(self):
        return self.conn.listDefinedNetworks()

    def net_status(self, uuid):
        return {
            0: 'notactive',
            1: 'running'
        }[self.conn.networkLookupByUUIDString(uuid).isActive()]

    def _add_disk(self, xml, disk):
        with xml.disk(type='file', device='disk', cache='writeback'):
            xml.driver(name='qemu', type='qcow2')
            xml.source(file=disk['source_file'])
            xml.target(
                dev=disk['target_dev'], bus=disk.get('target_bus', 'scsi'))

    def _add_interface(self, xml, interface):
        itype = interface.get('type', 'network')
        with xml.interface(type=itype):
            if itype == 'bridge':
                xml.source(bridge=interface['source_bridge'])
            elif itype == 'network':
                xml.source(network=interface['source_network'])
            xml.model(type=interface.get('model_type', 'e1000'))
            if interface.get('mac_address'):
                xml.mac(address=interface['mac_address'])
            if interface.get('virtualport_type'):
                xml.virtualport(type=interface['virtualport_type'])

    def define(self, name, uuid=None, type='kvm', memory='2048', vcpu='1',
               arch='x86_64', boot=None, disks=None, interfaces=None):
        xml = xmlbuilder.XMLBuilder('domain', type=type)
        xml.name(name)
        if uuid:
            xml.uuid(uuid)

        xml.memory(memory, unit='MiB')
        xml.vcpu(vcpu)

        with xml.os:
            xml.type('hvm', arch=arch, machine='pc-1.0')
            if boot:
                if isinstance(boot, (list, tuple)):
                    for dev in boot:
                        xml.boot(dev=dev)
                elif isinstance(boot, (str, unicode)):
                    xml.boot(dev=boot)
            xml.bootmenu(enable='no')

        with xml.features:
            xml.acpi
            xml.apic
            xml.pae
        xml.clock(offset='utc')
        xml.on_poweroff('destroy')
        xml.on_reboot('restart')
        xml.on_crash('restart')

        with xml.devices:
            if os.path.exists('/usr/bin/kvm'):  # Debian
                xml.emulator('/usr/bin/kvm')
            elif os.path.exists('/usr/bin/qemu-kvm'):  # Redhat
                xml.emulator('/usr/bin/qemu-kvm')

            xml.input(type='mouse', bus='ps2')
            xml.graphics(type='vnc', port='-1', autoport='yes')
            with xml.video:
                xml.model(type='cirrus', vram='9216', heads='1')
                xml.address(type='pci', domain='0x0000',
                            bus='0x00', slot='0x02', function='0x0')
            with xml.memballoon(model='virtio'):
                xml.address(type='pci', domain='0x0000',
                            bus='0x00', slot='0x07', function='0x0')

            if disks:
                if isinstance(disks, (list,)):
                    for disk in disks:
                        self._add_disk(xml, disk)
                else:
                    self._add_disk(xml, disks)

            if interfaces:
                if isinstance(interfaces, (list,)):
                    for interface in interfaces:
                        self._add_interface(xml, interface)
                else:
                    self._add_interface(xml, interfaces)

        dom = self.conn.defineXML(str(xml))
        return dom.UUIDString()

    def destroy(self, uuid):
        dom = self.conn.lookupByUUIDString(uuid)
        dom.destroy()

    def start(self, uuid):
        dom = self.conn.lookupByUUIDString(uuid)
        dom.create()

    def undefine(self, uuid):
        dom = self.conn.lookupByUUIDString(uuid)
        dom.undefine()

    def list(self):
        return (
            self.conn.listDefinedDomains() +
            [self.conn.lookupByID(dom).name()
             for dom in self.conn.listDomainsID()]
        )

    def list_active(self):
        return [self.conn.lookupByID(dom).name()
                for dom in self.conn.listDomainsID()]

    def list_notactive(self):
        return self.conn.listDefinedDomains()

    def uuid_by_name(self, name):
        dom = self.conn.lookupByName(name)
        return dom.UUIDString()

    def status(self, uuid):
        states = {
            libvirt.VIR_DOMAIN_NOSTATE: 'nostate',
            libvirt.VIR_DOMAIN_RUNNING: 'running',
            libvirt.VIR_DOMAIN_BLOCKED: 'blocked',
            libvirt.VIR_DOMAIN_PAUSED: 'paused',
            libvirt.VIR_DOMAIN_SHUTDOWN: 'shutdown',
            libvirt.VIR_DOMAIN_SHUTOFF: 'shutoff',
            libvirt.VIR_DOMAIN_CRASHED: 'crashed',
            libvirt.VIR_DOMAIN_PMSUSPENDED: 'suspended',
        }

        dom = self.conn.lookupByUUIDString(uuid)
        return states.get(dom.state()[0], 'unknown')

    def pool_define(self, name, path):
        xml = xmlbuilder.XMLBuilder('pool', type='dir')
        xml.name(name)
        with xml.target:
            xml.path(path)
        if not os.path.isdir(path):
            os.makedirs(path, 0o755)
        return self.conn.storagePoolCreateXML(str(xml)).UUIDString()

    def pool_list(self):
        return (self.conn.listDefinedStoragePools() +
                self.conn.listStoragePools())

    def pool_list_active(self):
        return self.conn.listStoragePools()

    def pool_list_notactive(self):
        return self.conn.listDefinedStoragePools()

    def pool_destroy(self, uuid):
        pool = self.conn.storagePoolLookupByUUIDString(uuid)
        pool.destroy()

    def pool_start(self, uuid):
        pool = self.conn.storagePoolLookupByUUIDString(uuid)
        pool.create()

    def pool_undefine(self, uuid):
        pool = self.conn.storagePoolLookupByUUIDString(uuid)
        pool.undefine()

    def pool_uuid_by_name(self, name):
        pool = self.conn.storagePoolLookupByName(name)
        return pool.UUIDString()

    def vol_create(self, name, capacity=None,
                   base=None, pool_name='default',
                   backing_store=False, base_plus=0):
        xml = xmlbuilder.XMLBuilder('volume')
        xml.name(name)
        xml.allocation('0', unit='MiB')
        if base:
            xml.capacity(str(int(get_qcow_size(base)) +
                             int(base_plus) * 1048576))
        else:
            xml.capacity(capacity, unit='MiB')

        with xml.target:
            xml.format(type='qcow2')

        pool = self.conn.storagePoolLookupByName(pool_name)
        if base and backing_store:
            with xml.backingStore:
                xml.path(base)
                xml.format(type='qcow2')

        vol = pool.createXML(str(xml), flags=0)

        if base and not backing_store:
            self.volume_upload(vol.key(), base)

        return vol.key()

    def vol_list(self, pool_name='default'):
        pool = self.conn.storagePoolLookupByName(pool_name)
        return pool.listVolumes()

    def vol_path(self, name, pool_name='default'):
        pool = self.conn.storagePoolLookupByName(pool_name)
        vol = pool.storageVolLookupByName(name)
        return vol.path()

    def vol_delete(self, name, pool_name='default'):
        pool = self.conn.storagePoolLookupByName(pool_name)
        vol = pool.storageVolLookupByName(name)
        vol.delete(flags=0)

    def chunk_render(self, stream, size, fd):
        return fd.read(size)

    def volume_upload(self, name, path):
        size = get_file_size(path)
        with open(path, 'rb') as fd:
            stream = self.conn.newStream(0)
            self.conn.storageVolLookupByKey(name).upload(
                stream=stream, offset=0,
                length=size, flags=0)
            stream.sendAll(self.chunk_render, fd)
            stream.finish()


def env_define(env, drv=None):
    if drv is None:
        drv = LibvirtDriver()

    LOG.debug('Defining environment: %s' % env.name)

    for network in env.networks:
        netname = env.name + '_' + network.name
        LOG.debug('Defining network: %s' % netname)
        network_kwargs = {
            'bridge_name': network.bridge,
            'forward_mode': 'nat',
            'ip_address': network.ip,
        }
        if env.tftp and env.tftp.network == network.name:
            network_kwargs['tftp_root'] = env.tftp.tftp_root
        if env.dhcp and env.dhcp.network == network.name:
            network_kwargs['dhcp'] = {
                'start': env.dhcp.start,
                'end': env.dhcp.end,
            }
            if env.dhcp.bootp:
                network_kwargs['dhcp']['bootp'] = env.dhcp.bootp
            if env.dhcp.hosts:
                network_kwargs['dhcp']['hosts'] = env.dhcp.hosts
        drv.net_define(netname, **network_kwargs)
        drv.net_start(drv.net_uuid_by_name(netname))


    for vm in env.vms:
        vmname = env.name + '_' + vm.name
        disks = []
        for num, disk in enumerate(vm.disks):
            disk_name = vmname + '_%s' % num
            order = 'abcdefghijklmnopqrstuvwxyz'
            if disk.base:
                drv.vol_create(disk_name, base=disk.base)
            else:
                drv.vol_create(disk_name, capacity=disk.size)
            disks.append({
                'source_file': drv.vol_path(disk_name),
                'target_dev': 'sd%s' % order[num],
                'target_bus': 'scsi',
            })
        interfaces = []
        for interface in vm.interfaces:
            interfaces.append({
                'type': 'network',
                'source_network': env.name + '_' + interface.network,
                'mac_address': interface.mac
            })
        drv.define(vmname, boot=vm.boot, disks=disks, interfaces=interfaces)
        drv.start(drv.uuid_by_name(vmname))


def env_undefine(env, drv=None):
    if drv is None:
        drv = LibvirtDriver()

    for vm in env.vms:
        vmname = env.name + '_' + vm.name
        if vmname in drv.list():
            uuid = drv.uuid_by_name(vmname)
            if vmname in drv.list_active():
                drv.destroy(uuid)
            drv.undefine(uuid)

        for volname in [v for v in drv.vol_list() if v.startswith(vmname)]:
            drv.vol_delete(volname)

    for network in env.networks:
        netname = env.name + '_' + network.name
        if netname in drv.net_list():
            uuid = drv.net_uuid_by_name(netname)
            if netname in drv.net_list_active():
                drv.net_destroy(uuid)
            drv.net_undefine(uuid)
