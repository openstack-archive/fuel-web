Fuel CI Explanation
===================

Components
----------

Nodes and roles
---------------

Currently we're defining roles via our puppet manifests we have few roles for nodes.
Those generic roles are defined in ``manifests/site.pp`` file:

 * PXEtool node
 * Puppet master
 * Jenkins slave
 * Jenkins master
 * Gerrit
 * Mirror
 * Seed instance
 * Zabbix server

Each role represents the component of the whole system which could require one
or more other components.

For example Jenkins slave requires Jenkins master.

Puppet
------

Puppet deploymen with Fuel Infra manifests require Puppet master.
To install Puppet master from the brand new server you should run
``bin/install_puppet_master.sh`` script which does the following:

 * uprgade all packages on the system
 * install required modules
 * install puppet and puppet master packages
 * run puppet apply to setup puppet master
 * run puppet agent to do a second pass and verify installation is usable

**NOTE** Puppet manifests are using data(like passwords or configuration) from
hiera. To start working with pregenerated test data you could simply copy/link
``hiera/common-example.yaml`` file to ``/var/lib/hiera/common.yaml``.
This step must be done before running ``bin/install_puppet_master.sh``.

Once it's done you could start deploying other nodes.

Gerrit
------

Jenkins
-------

Tests
-----

