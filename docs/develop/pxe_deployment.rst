Fuel Master Node Deployment over PXE
====================================

Tech Explanation of the process
-------------------------------
In some cases (such as no installed CD-ROM or no physical access to the
servers) we need to install Fuel Master node somehow other way from CD or USB
Flash drive. Starting from Fuel 4.0 it's possible to deploy Master node with PXE

The process of deployment of Fuel master node over network consists of booting
linux kernel by DHCP and PXE. Then anaconda installer will download
configuration file and all packages needed to complete the installation.

 * PXE firmware of the network card makes DHCP query and gets IP address and 
   boot image name.
 * Firmware downloads boot image file using TFTP protocol and starts it.
 * This bootloader downloads configuration file with kernel boot option, 
   kernel and initramfs and starts the installer.
 * Installer downloads kickstart configuration file by mounting contents of 
   Fuel ISO file over NFS.
 * Installer partitions hard drive, installs the system by downloading packages 
   over NFS, copies all additional files, installs the bootloader and reboots 
   into new system. 

So we need:
 * Working system to serve as network installer.
 * DHCP server
 * TFTP server
 * NFS server
 * PXE bootloader and its configuration file
 * Extracted or mounted Fuel ISO file

In our test we will use 10.20.0.0/24 network.
10.20.0.1/24 will be IP address of our host system.

Installing packages
-------------------
We will be using Ubuntu or Debian system as an installation server. Other linux
or even BSD-based systems could be used too, but paths to configuration files
and init scripts may differ.

First we need to install the software::

    # TFTP server and client
    apt-get install tftp-hpa tftpd-hpa
    # DHCP server
    apt-get install isc-dhcp-server
    # network bootloader
    apt-get install syslinux syslinux-common
    # nfs server
    apt-get install nfs-server

Setting up DHCP server
--------------------------
Standalone ISC DHCPD
~~~~~~~~~~~~~~~~~~~~
First we are going to create configuration file located at /etc/dhcp/dhcpd.conf::

    ddns-update-style none;
    default-lease-time 600;
    max-lease-time 7200;
    authoritative;
    log-facility local7;

    subnet 10.20.0.0 netmask 255.255.255.0 {
        range 10.20.0.2 10.20.0.2;
        option routers 10.20.0.1;
        option domain-name-servers 10.20.0.1;
    }

    host fuel {
        hardware ethernet 52:54:00:31:38:5a;
        fixed-address 10.20.0.2;
        filename "pxelinux.0";
    }

We have declared a subnet with only one IP address available that we are going
to give to our master node. We are not going to serve entire range of IP
addresses because it will disrupt Fuel’s own DHCP service. There is also a host
definition with a custom configuration that matches a specific MAC address. This
address should be set to the MAC address of the system that you are going to
make Fuel master node. Other systems on this subnet will not receive any IP
addresses and will load bootstrap from master node when it starts serving DHCP
requests.
We also give a filename that will be used to boot the Fuel master node.


Using 10.20.0.0/24 subnet requires you to set 10.20.0.1 on the network
interface connected to this network. You may also need to set the interface
manually using the INTERFACES variable in /etc/default/isc-dhcp-server file.

Start DHCP server::

    /etc/init.d/isc-dhcp-server restart

Simple with dnsmasq::

    sudo dnsmasq -d --enable-tftp --tftp-root=/var/lib/tftpboot \
        --dhcp-range=10.20.0.2,10.20.0.2  \
        --port=0 -z -i eth2 \
        --dhcp-boot='pxelinux.0'

Libvirt with dnsmasq
~~~~~~~~~~~~~~~~~~~~
If you are using libvirt virtual network to install your master node, then you
can use its own DHCP service. Use virsh net-edit default to modify network
configuration::

    <network>
        <name>default</name>
        <bridge name="virbr0" />
        <forward />
        <ip address="10.20.0.1" netmask="255.255.255.0">
            <tftp root="/var/lib/tftpboot"/> 
            <dhcp>
                <range start="10.20.0.2" end="10.20.0.2" />
                <host mac="52:54:00:31:38:5a" ip="10.20.0.2" />
                <bootp file="pxelinux.0"/>           
            </dhcp>
        </ip>
    </network>

This configuration includes TFTP server and DHCP server with only one IP
address set to your master node’s MAC address. You don't need to install
neither external DHCP server nor TFTP server.
Don’t forget to restart the network after making edits::

    virsh net-destroy default
    virsh net-start default

Dnsmasq without libvirt
~~~~~~~~~~~~~~~~~~~~~~~
You can also use dnsmasq as a DHCP and TFTP server without libvirt::

    strict-order
    domain-needed
    user=libvirt-dnsmasq
    local=//
    pid-file=/var/run/dnsmasq.pid
    except-interface=lo
    bind-dynamic
    interface=virbr0
    dhcp-range=10.20.0.2,10.20.0.2
    dhcp-no-override
    enable-tftp
    tftp-root=/var/lib/tftpboot
    dhcp-boot=pxelinux.0
    dhcp-leasefile=/var/lib/dnsmasq/leases
    dhcp-lease-max=1
    dhcp-hostsfile=/etc/dnsmasq/hostsfile

In /etc/dnsmasq/hostsfile you can specify hosts and their mac addresses::

    52:54:00:31:38:5a,10.20.0.2

Dnsmasq provides both DHCP, TFTP, as well as acts as a DNS caching server, so
you don't need to install additional external services.

Setting our TFTP server
-----------------------
If you are not using a libvirt virtual network, then you need to install tftp
server. On Debian or Ubuntu system its configuration file will be located here
/etc/default/tftpd-hpa.
Checking if all we want are there::

    TFTP_USERNAME="tftp"
    TFTP_DIRECTORY="/var/lib/tftpboot"
    TFTP_ADDRESS="10.20.0.1:69"
    TFTP_OPTIONS="--secure --blocksize 512"

Don’t forget to set blocksize here. Some hardware switches have problems with
larger block sizes.
And star it::

    /etc/init.d/tftpd-hpa restart

Setting up NFS server
---------------------
You will also need to setup NFS server on your install system. Edit the NFS
exports file::

    vim /etc/exports

Add the following line::

    /var/lib/tftpboot 10.20.0.2(ro,async,no_subtree_check,no_root_squash,crossmnt)

And start it::

    /etc/init.d/nfs-kernel-server restart


Set up tftp root
----------------
Our tftp root will be located here: /var/lib/tftpboot
Let’s create a folder called "fuel" to store ISO image contents and syslinux
folder for bootloader files. If you have installed syslinux package you can find
them in /usr/lib/syslinux folder.
Copy this files from /usr/lib/syslinux to /var/lib/tftpboot::

    memdisk  menu.c32  poweroff.com  pxelinux.0  reboot.c32

Now we need to write the pxelinux configuration file. It will be located here
/var/lib/tftpboot/pxelinux.cfg/default::

    DEFAULT menu.c32
    prompt 0
    MENU TITLE My Distro Installer

    TIMEOUT 600

    LABEL localboot
    MENU LABEL ^Local Boot
    MENU DEFAULT
    LOCALBOOT 0

    LABEL fuel
    MENU LABEL Install ^FUEL
    KERNEL /fuel/isolinux/vmlinuz
    INITRD /fuel/isolinux/initrd.img
    APPEND biosdevname=0 ks=nfs:10.20.0.1:/var/lib/tftpboot/fuel/ks.cfg repo=nfs:10.20.0.1:/var/lib/tftpboot/fuel ip=10.20.0.2 netmask=255.255.255.0 gw=10.20.0.1 dns1=10.20.0.1 hostname=fuel.mirantis.com showmenu=no

    LABEL reboot
    MENU LABEL ^Reboot
    KERNEL reboot.c32

    LABEL poweroff
    MENU LABEL ^Poweroff
    KERNEL poweroff.com

You can ensure silent installation without any Anaconda prompts by adding the following APPEND directives:

* ksdevice=INTERFACE
* installdrive=DEVICENAME
* forceformat=yes

For example:

    installdrive=sda ksdevice=eth0 forceformat=yes

Now we need to unpack the Fuel ISO file we have downloaded::

    mkdir -p /var/lib/tftpboot/fuel /mnt/fueliso
    mount -o loop /path/to/your/fuel.iso /mnt/fueliso
    rsync -a /mnt/fueliso/ /var/lib/tftpboot/fuel/
    umount /mnt/fueliso && rmdir /mnt/fueliso

So that's it! We can boot over the network from this PXE server.

Troubleshooting
---------------

After implementing one of the described configuration you should see something
like that in your /var/log/syslog file::

    dnsmasq-dhcp[16886]: DHCP, IP range 10.20.0.2 -- 10.20.0.2, lease time 1h
    dnsmasq-tftp[16886]: TFTP root is /var/lib/tftpboot

To make sure all of daemon listening sockets as they should::

 # netstat -upln | egrep ':(67|69|2049) '
 udp        0      0 0.0.0.0:67              0.0.0.0:*                           30791/dnsmasq
 udp        0      0 10.20.0.1:69            0.0.0.0:*                           30791/dnsmasq
 udp        0      0 0.0.0.0:2049            0.0.0.0:*                           -

* NFS - udp/2049
* DHCP - udp/67
* TFTP - udp/69

So all of daemons listening as they should.

To test DHCP server does provide an IP address you can do something like that
on the node in the defined PXE network.  Please note, it should have Linux
system installed or any other OS to test configuration properly::

    # dhclient -v eth0
    Internet Systems Consortium DHCP Client 4.1.1-P1
    Copyright 2004-2010 Internet Systems Consortium.
    All rights reserved.
    For info, please visit https://www.isc.org/software/dhcp/

    Listening on LPF/eth0/00:25:90:c4:7a:64
    Sending on   LPF/eth0/00:25:90:c4:7a:64
    Sending on   Socket/fallback
    DHCPREQUEST on eth0 to 255.255.255.255 port 67 (xid=0x7b6e25dc)
    DHCPACK from 10.20.0.1 (xid=0x7b6e25dc)
    bound to 10.20.0.2 -- renewal in 1659 seconds.

After running dhclient you should see how it asks one or few times DHCP server
with DHCPDISCOVER and then get 10.20.0.2.  If you have more then one NIC you
should run dhclient on every one to determine where our network in connected
to.

TFTP server can be tested with tftp console client::

    # tftp
    (to) 10.20.0.1
    tftp> get /pxelinux.0

NFS could be tested with mounting it::

    mkdir /mnt/nfsroot
    mount -t nfs 10.20.0.1:/var/lib/tftpboot /mnt/nfsroot

