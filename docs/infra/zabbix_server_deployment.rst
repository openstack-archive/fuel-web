Zabbix server
=============

Zabbix is an open source tool designed for servers, services and network
monitoring.

Deployment
----------

Zabbix can be deployed on a virtual machine having at least 1GB of RAM/1 CPU.
The HW requirements vary, and depends on the potential zabbix load and
place of the database engine (MySQL for instance) - would it be on the same
host or on a dedicated one.

The puppet-manifests repository contains an example zabbix role 'zbxserver'
which could be used as a starting point for Zabbix deployment.

Now proceed the following steps for the deployment.

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

The last action requests the certificate from Puppet Master first, on which
the signing of the client's certificate must be completed, in order to continue
the puppet run.

Import templates
----------------

It is possible to import templates and related items, triggers that comes from
Fuel's Zabbix production server. To do so it is required to clone the respository
storing the data, and then import the templates using the web UI.

#. Clone 'tools/zabbix-maintenance' repository:

   .. code-block:: console

     git clone https://review.fuel-infra.org/tools/zabbix-maintenance

#. Login to your zabbix web UI, navigate to 'Configuration->Templates' and click
   the import button to choose the template file.