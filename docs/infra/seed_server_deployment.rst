Seed server
===========

Seed server serves the files, such as ISO and disk images that were uploaded
from other servers or clients. Seed can host the content by the rsync, http,
or torrent protocol, depending on the Hiera's role configuration.

Deployment
----------

Before you deploy Seed server, verify that you have completed the following tasks:

#. Deploy the Puppet Master
#. Verify that the DNS solution works.
#. On the Puppet Master, create ``seed``, a dedicated Hiera role from which all necessary services as opentracker will install.

.. note::
   For torrent download, do not include the ``fuel_project::apps::mirror``

#. On the Jenkins Master, verify that the ``seed`` Hiera role exists:

   .. code-block:: ini

     ---
     classes:
       - 'fuel_project::common'
       - 'fuel_project::apps::seed'
       - 'fuel_project::apps::firewall'
       - 'opentracker'

     fuel_project::apps::seed::vhost_acl_allow:
       - 10.0.0.2/32 # IP's slave example on which ISO is build

     fuel_project::apps::seed::service_fqdn: 'seed.test.local'

     fuel_project::apps::seed::seed_cleanup_dirs:
       - dir: '/var/www/seed/fuelweb-iso'
         ttl: 11
         pattern: 'fuel-*'

     fuel_project::apps::firewall::rules:
       '1000 - allow ssh connections from 0.0.0.0/0':
         source: 0.0.0.0/0
         dport: 22
         proto: tcp
         action: accept

       '1000 - allow data upload connections from temp build1.test.local':
         source: 10.0.0.2/32
         dport: 17333
         proto: tcp
         action: accept

       '1000 - allow zabbix-agent connections from 10.0.0.200/32':
         source: 10.0.0.200/32
         dport: 10050
         proto: tcp
         action: accept

       '1000 - allow torrent traffic within 10.0.0.0/8 network':
         source: 10.0.0.0/8
         dport: 8080
         proto: tcp
         action: accept

To deploy Seed server, complete the following steps:

#. Install base Ubuntu 14.04 with SSH service and set appropriate FQDN.

#. Install puppet agent package:

   .. code-block:: console

     apt-get update; apt-get install -y puppet

#. Enable puppet agent:

   .. code-block:: console

     puppet agent --enable

#. Run the deployment of the ``seed`` role:

   .. code-block:: console

     FACTER_ROLE=seed FACTER_LOCATION=us1 puppet agent -tvd \
     --server puppet-master.test.local --waitforcert 60

The last action requests the client's certificate, which has to be signed from
the Puppet Master, in order to continue the puppet run.
