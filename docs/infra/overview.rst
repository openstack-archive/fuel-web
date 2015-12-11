Fuel Infrastructure
===================

Overview
--------

Fuel Infrastructure is the set of systems (servers and services) which provide
the following functionality:

* automatic tests for every patchset commited to Fuel Gerrit repositories,
* Fuel nightly builds,
* regular integration tests,
* custom builds and custom tests,
* release management and publishing,
* small helper subsystems like common ZNC-bouncer, status pages and so on.

Fuel Infrastructure servers are managed by Puppet from one Puppet Master node.

To add new server to the infrastructure you can either take any server with base
Ubuntu 14.04 installed and connect it to the Puppet Master via puppet agent, or
you can first set up the PXE-server with PXETool :ref:`pxe-tool` and then run
server provisioning in automated way.

Your infrastructure must be running a DNS service in order to resolve the
mandatory hosts like puppet-master.test.local or pxetool.test.local. There are
at least two possible scenarios regarding DNS in your infra.
Using DHCP service in your infra is optional, but can be more elastic and
comfortable than static IP configuration.

#. 1) Create own DNS service provided by dnsmasq in your infra

   # Install base Ubuntu 14.04 with SSH service and set appropriate FQDN like
   # dns01.test.local and configure Dnsmasq service.

   ::

     # apt-get update; apt-get install -y dnsmasq

     # echo "addn-hosts=/etc/dnsmasq.d/hosts" >> /etc/dnsmasq.conf

     # echo "192.168.50.2 puppet-master.test.local puppet-master" > /etc/dnsmasq.d/hosts

     # echo "192.168.50.3 pxetool.test.local puppet-master" > /etc/dnsmasq.d/hosts

     # service dnsmasq restart

     # Ensure to update /etc/resolv.conf file to point to your DNS if using
     # static IP configuration or update DHCP service in case of dynamic

#. 2) Add new zone to your current DNS setup or use external, online DNS service

   ::

     # Add a zone named 'test.local'

     # Add appropriate A and its coresponding PTR record for 'puppet-master'
     # name (mandatory for deployment) at least

     # Ensure to update /etc/resolv.conf file to point to your DNS if using
     # static IP configuration or update DHCP service in case of dynamic


