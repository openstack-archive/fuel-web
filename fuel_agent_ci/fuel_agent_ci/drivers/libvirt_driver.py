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


def net_start(net, drv=None):
    if drv is None:
        drv = LibvirtDriver()
    LOG.debug('Starting network: %s' % net.name)
    netname = net.env.name + '_' + net.name
    net_kwargs = {
        'bridge_name': net.bridge,
        'forward_mode': 'nat',
        'ip_address': net.ip,
    }
    tftp = net.env.tftp_by_network(net.name)
    if tftp:
        net_kwargs['tftp_root'] = os.path.join(
            net.env.envdir, tftp.tftp_root)
    dhcp = net.env.dhcp_by_network(net.name)
    if dhcp:
        net_kwargs['dhcp'] = {
            'start': dhcp.begin,
            'end': dhcp.end,
        }
        if dhcp.bootp:
            net_kwargs['dhcp']['bootp'] = dhcp.bootp
        if dhcp.hosts:
            net_kwargs['dhcp']['hosts'] = dhcp.hosts
    drv.net_define(netname, **net_kwargs)
    drv.net_start(drv.net_uuid_by_name(netname))


def net_stop(net, drv=None):
    if drv is None:
        drv = LibvirtDriver()
    LOG.debug('Stopping net: %s' % net.name)
    netname = net.env.name + '_' + net.name
    if netname in drv.net_list():
        uuid = drv.net_uuid_by_name(netname)
        if netname in drv.net_list_active():
            drv.net_destroy(uuid)
        drv.net_undefine(uuid)


def net_status(net, drv=None):
    if drv is None:
        drv = LibvirtDriver()
    return (net.env.name + '_' + net.name in drv.net_list_active())


def vm_start(vm, drv=None):
    if drv is None:
        drv = LibvirtDriver()
    LOG.debug('Starting vm: %s' % vm.name)
    vmname = vm.env.name + '_' + vm.name

    if vm.env.name not in drv.pool_list():
        LOG.debug('Defining volume pool %s' % vm.env.name)
        drv.pool_define(vm.env.name, os.path.join(vm.env.envdir, 'volumepool'))
    if vm.env.name not in drv.pool_list_active():
        LOG.debug('Starting volume pool %s' % vm.env.name)
        drv.pool_start(drv.pool_uuid_by_name(vm.env.name))

    disks = []
    for num, disk in enumerate(vm.disks):
        disk_name = vmname + '_%s' % num
        order = 'abcdefghijklmnopqrstuvwxyz'
        if disk_name not in drv.vol_list(pool_name=vm.env.name):
            if disk.base:
                LOG.debug('Creating vm disk: pool=%s vol=%s base=%s' %
                          (vm.env.name, disk_name, disk.base))
                drv.vol_create(disk_name, base=disk.base,
                               pool_name=vm.env.name)
            else:
                LOG.debug('Creating empty vm disk: pool=%s vol=%s '
                          'capacity=%s' % (vm.env.name, disk_name, disk.size))
                drv.vol_create(disk_name, capacity=disk.size,
                               pool_name=vm.env.name)
        disks.append({
            'source_file': drv.vol_path(disk_name, pool_name=vm.env.name),
            'target_dev': 'sd%s' % order[num],
            'target_bus': 'scsi',
        })

    interfaces = []
    for interface in vm.interfaces:
        LOG.debug('Creating vm interface: net=%s mac=%s' %
                  (vm.env.name + '_' + interface.network, interface.mac))
        interfaces.append({
            'type': 'network',
            'source_network': vm.env.name + '_' + interface.network,
            'mac_address': interface.mac
        })
    LOG.debug('Defining vm %s' % vm.name)
    drv.define(vmname, boot=vm.boot, disks=disks, interfaces=interfaces)
    LOG.debug('Starting vm %s' % vm.name)
    drv.start(drv.uuid_by_name(vmname))


def vm_stop(vm, drv=None):
    if drv is None:
        drv = LibvirtDriver()
    LOG.debug('Stopping vm: %s' % vm.name)
    vmname = vm.env.name + '_' + vm.name
    if vmname in drv.list():
        uuid = drv.uuid_by_name(vmname)
        if vmname in drv.list_active():
            LOG.debug('Destroying vm: %s' % vm.name)
            drv.destroy(uuid)
        LOG.debug('Undefining vm: %s' % vm.name)
        drv.undefine(uuid)

    for volname in [v for v in drv.vol_list(pool_name=vm.env.name)
                    if v.startswith(vmname)]:
        LOG.debug('Deleting vm disk: pool=%s vol=%s' % (vm.env.name, volname))
        drv.vol_delete(volname, pool_name=vm.env.name)

    if not drv.vol_list(pool_name=vm.env.name):
        LOG.debug('Deleting volume pool: %s' % vm.env.name)
        if vm.env.name in drv.pool_list():
            uuid = drv.pool_uuid_by_name(vm.env.name)
            if vm.env.name in drv.pool_list_active():
                LOG.debug('Destroying pool: %s' % vm.env.name)
                drv.pool_destroy(uuid)
            if vm.env.name in drv.pool_list():
                LOG.debug('Undefining pool: %s' % vm.env.name)
                drv.pool_undefine(uuid)


def vm_status(vm, drv=None):
    if drv is None:
        drv = LibvirtDriver()
    return (vm.env.name + '_' + vm.name in drv.list_active())


def dhcp_start(dhcp):
    """This feature is implemented in net_start
    """
    pass


def dhcp_stop(dhcp):
    """This feature is implemented is net_stop
    """
    pass


def dhcp_status(dhcp):
    return dhcp.env.net_by_name(dhcp.network).status()


def tftp_start(tftp):
    """This feature is implemented is net_start
    """
    pass


def tftp_stop(tftp):
    """This feature is implemented is net_stop
    """
    pass


def tftp_status(tftp):
    return tftp.env.net_by_name(tftp.network).status()
