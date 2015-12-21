Seed server
===========

Overview
--------

Seed server's role is to serve files uploaded from other servers, or
clients, like ISO, disks images. Seed can host the content by the rsync,
http or torrent protocol, depending on the Hiera's role configuration.

Deployment
----------

To deploy Seed server it is required to have Puppet Master already deployed
and already working DNS solution. It is required also to create a dedicated Hiera
role - 'seed' - on a Puppet Master, from which necessary services like
opentracker will be installed.

Note: for torrent download only it is not required to include the
'fuel_project::apps::mirror' class.

#. Ensure in jenkins master to have the following 'seed' hiera role.

   ::

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

Now proceed with the following steps for the deployment.

#. Install base Ubuntu 14.04 with SSH service and set appropriate FQDN.

#. Install puppet agent package.

   ::

     apt-get update; apt-get install -y puppet

#. Enable puppet agent.

   ::

     puppet agent --enable

#. Run deployment of the Seed's role.

   ::

     FACTER_ROLE=seed FACTER_LOCATION=us1 puppet agent -tvd \
     --server puppet-master.test.local --waitforcert 60

The last action will requests the certificate from Puppet Master first, on which
the signing of the client's certificate must be completed, in order to continue
the puppet run.
