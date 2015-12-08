Puppet Master
=============

--------
Overview
--------

Puppet is a tool which provide ability to manage configuration of systems in an
automatic way using the declarative language. The so called 'manifests' are
used for describing particular system configuration.

------------------------
Puppet master deployment
------------------------

In order to install Puppet Master to the brand new server running Ubuntu please
proceed with the following steps:

#. Install Ubuntu 14.04 with SSH service and set FQDN to puppet-master.test.local

#. Install git and clone Puppet Manifests repository into /etc/puppet directory

   ::

     # apt-get install -y git
     # git clone https://github.com/fuel-infra/puppet-manifests.git /etc/puppet

#. Execute the Puppet Master's install script

   ::

     # /etc/puppet/bin/install_puppet_master.sh

The script does the following:

* upgrades all packages on the system
* installs required puppet modules
* installs Puppet Master packages
* runs puppet apply to setup Puppet Master
* runs puppet agent to do a second pass and verify if installation is usable

When script finishes successfully, the Puppet Master installation is completed.

-----------
Using Hiera
-----------

Puppet can use Hiera to look up for data. Hiera allows to override manifest
parameter values during the deployment, thus it is possible to create
a specific data configuration for easier code re-use and easier management of
data that needs to differ across nodes.
All related Hiera structure is placed under the /var/lib/hiera directory.


The Hiera hierarchy
-------------------

    #. common.yaml - the most general,
    #. locations/%{::location}.yaml - can override common's data,
    #. roles/%{::role}.yaml - can override location's and common's data
    #. nodes/%{::clientcert}.yaml - can override data specified in common,
    #. location and role.

The common and nodes are used within every deployment when exist. But in
contrast, the location and role needs to be passed explicitly as a variable
within puppet agent run, in order to use them. Example:

   ::

     #. FACTER_ROLE=websrv FACTER_LOCATION=us1 puppet agent -tvd

To include puppet's class in a role, it is required to use the 'classes'
keyword on the role's beginning. An example:

   ::

     #. classes:
     #. - '::class1::class2'

Note: avoid including classes in more than one place since this will lead to
class duplicate declaration error.

Other example - create a role's stub for 'docker_registry' module and make
sure that each of the nodes running that role have its own, custom, service's
FQDN set in Nginx's Vhost.

  #. roles/docker_registry.yaml

   ::

     #. ---
     #. classes:
     #. - '::docker_registry'
     #. - '::fuel_project::nginx'
     #. - '::fuel_project::apps::firewall'
     #. - '::fuel_project::common'
     #.
     #. docker_registry::service_fqdn: '%{::fqdn}'

  #. nodes/srv01-us.infra.test.local.yaml

   ::

     #. ---
     #.
     #. docker_registry::service_fqdn: 'registry-us1.infra.test.local'

  #. nodes/srv01-cz.infra.test.local.yaml

   ::

     #. ---
     #.
     #. docker_registry::service_fqdn: 'registry-cz1.infra.test.local'

On a node srv01-us.infra.test.local during the deployment of a 'docker_registry' role
a default value for 'service_fqdn' class parameter has been overridden.

After the deployment using FACTER variable a facter file will be created
containing the used FACTERs variables. For instance:

   ::

     #. cat /etc/facter/facts.d/facts.sh
     #. !/bin/bash
     #.
     #. echo "location=us1"
     #. echo "role=docker_registry"

Having these, now every next puppet agent run will not require FACTER variables
to be passed (if no role nor location is to be changed).
