Zabbix server
=============

Zabbix is an open source tool designed for servers, services, and network
monitoring.

Deployment
----------

Zabbix can be deployed on a virtual machine with at least 1 GB RAM and one CPU.
The HW requirements vary and depend on the potential Zabbix's server load and
place of the database engine, for example, MySQL, regardless of whether is
located - on the same host or on a dedicated one.

The puppet-manifests repository contains an example ``zbxserver`` role
that can be used as a starting point for Zabbix server deployment.

To deploy Zabbix, perform the following tasks:

#. Install base Ubuntu 14.04 with SSH service and set appropriate FQDN.

#. Install puppet agent package:

   .. code-block:: console

     apt-get update; apt-get install -y puppet

#. Enable puppet agent:

   .. code-block:: console

     puppet agent --enable

#. Run the Jenkins Master deployment:

   .. code-block:: console

     FACTER_ROLE=zbxserver FACTER_LOCATION=us1 puppet agent -tvd \
     --server puppet-master.test.local --waitforcert 60

The last action requests the client's certificate, which has to be signed from
the Puppet Master, in order to continue the puppet run.

Import templates
----------------

It is possible to import templates and related items, triggers that comes from
Fuel's Zabbix production server. To do so it is required to clone the respository
which is storing the data, and then import the templates using the web UI.

#. Clone 'tools/zabbix-maintenance' repository:

   .. code-block:: console

     git clone https://review.fuel-infra.org/tools/zabbix-maintenance

#. Login to the Zabbix server web UI, navigate to 'Configuration->Templates' and click
   the import button to choose the template file.