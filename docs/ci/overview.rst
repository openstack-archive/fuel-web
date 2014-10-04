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
Ubuntu 14.04 installed and connect it to the Puppet master via puppet agent, or
you can first set up the PXE-server with PXETool (see below) and then run server
provisioning in automated way.

Puppet
------

Puppet master
~~~~~~~~~~~~~

Puppet deployment with Fuel Infra manifests requires Puppet master.
To install Puppet master to the brand new server
 * install base Ubuntu 14.04, define the initial configuration in
 * /var/lib/hiera/common.yaml,
 * run ``bin/install_puppet_master.sh``.

The script does the following:

 * upgrades all packages on the system
 * installs required modules
 * installs puppet and puppet master packages
 * runs puppet apply to setup puppet master
 * runs puppet agent to do a second pass and verify installation is usable

.. note:: Puppet manifests take data (passwords, keys or configuration
parameters) from
  hiera configuration. To work with predefined test data you could simply put
  ``hiera/common-example.yaml`` file to ``/var/lib/hiera/common.yaml``.
  This step must be done before running ``bin/install_puppet_master.sh``.

Once it is done you can start deploying other nodes.

Nodes and Roles
~~~~~~~~~~~~~~~

Currently we define server roles via our puppet manifests(link to repo). We have
several roles defined in ``manifests/site.pp`` file:

 * PXEtool node
 * Puppet master
 * Jenkins slave
 * Jenkins master
 * Gerrit
 * Mirror
 * Seed instance
 * Zabbix server

Jenkins
-------

Our Jenkins instances are configured to run in master-slave mode. We have
Jenkins master instance on a virtual machine and number of hardware nodes
working as Jenkins slaves.

Jenkins slaves setup
~~~~~~~~~~~~~~~~~~~~

There are several ways to setup Jenkins master-slave connection, and we use two
of them. The first one is organized simply by putting Jenkins master SSH-key in
authorized_keys file for jenkins user on a slave machine. Then you go to the
Jenkins Web UI and create node manually by specifying node IP address. Jenkins
master connects to the slave via SSH, downloads slave.jar file and runs jenkins
process on a slave.

The second approach requires more configuration but allows you to create slave
node automatically from the slave node itself. To use it you need:
    * install Swarm Plugin on Jenkins master,
    * create Jenkins user with ability to create nodes,
    * install jenkins-swarm-slave package on the slave,
    * configure the slave to use the mentioned Jenkins user,
    * run jenkins-swarm-slave service on the slave.

Service will automatically connect to Jenkins master and create node with proper
name and IP address.

Though this approach seems to be complicated it is quite easy to implement it
with Puppet, as we do in jenkins::slave Puppet class(link).

The downside of the swarm slave plugin is that every time you reboot Jenkins
master instance, slaves are recreated and, therefore, lose all the labels
assigned to them via Jenkins WebUI.

Gerrit
------

Although fuel-* repositories are hosted by the OpenStack Gerrit
http://review.openstack.org, we use additional Gerrit instance to host OpenStack
packages, internal projects and all the code related to Infrastructure itself.

Our Gerrit instance is installed and configured by Puppet, including specifying
the exact Java WAR file that is used(link). To manage Gerrit instance we use
Jeepyb - the tool written by Openstack Infra team, which allows to store
projects configuration in YAML format.

To use Jeepyb with gerrit you need to create "projects.yaml" configuration file,
where for each project you add the following information:

 * project name
 * project description
 * project ACL
 * project upstream

For more info about Jeepyb configuration refer to
http://ci.openstack.org/jeepyb.html

If "upstream" option is specified, Jeepyb will automaticaly import the upstream
repository to this new project.
To apply the configuration use "manage-projects" command.

Every project has ACL file. One ACL file can be reused in several projects. In
ACL file access rights are defined based on the Gerrit user groups.
For example, in this file you can allow certain group to use the Code-Review
+/-2 marks.

In our gerrit we have some global projects - <projects>/. The Core Reviewers for
these projects are <one-core-group>.

Contributing
~~~~~~~~~~~~

Feedback
~~~~~~~~
