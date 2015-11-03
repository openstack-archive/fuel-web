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
you can first set up the PXE-server with PXETool :ref:`pxe-tool` and then run server
provisioning in automated way.

Puppet
------

.. _pxe-tool:

Puppet Master
~~~~~~~~~~~~~


Puppet deployment with Fuel Infra manifests requires Puppet Master.
To install Puppet Master to the brand new server:

#. Get required repository with Puppet configuration:

   ::

     git clone ssh://(gerrit_user_name)@review.fuel-infra.org:29418/fuel-infra/puppet-manifests

#. Create a script to update puppet server to current version:

   ::

     #!/bin/bash

     REPO='/home/user/puppet-manifests'
     SERVER='pxetool'
     # sync repo files
     rsync -av --delete $REPO/modules/ root@$SERVER:/etc/puppet/modules/
     rsync -av --delete $REPO/manifests/ root@$SERVER:/etc/puppet/manifests/
     rsync -av --delete $REPO/bin/ root@$SERVER:/etc/puppet/bin/
     rsync -av --delete $REPO/hiera/ root@$SERVER:/etc/puppet/hiera/
     # create symlinks
     ssh root@$SERVER ln -s /etc/puppet/hiera/common-example.yaml /var/lib/hiera/common.yaml 2> /dev/null

#. Install base Ubuntu 14.04 with SSH server running (set hostname to pxetool.test.local).
   Download and install Puppet Agent package.

#. Run previously created script on your workstation to push configuration and scripts
   to new server.  Run /etc/puppet/bin/install_puppet_master.sh as root on new server.

The last script does the following:

* upgrades all packages on the system
* installs required modules
* installs puppet and Puppet Master packages
* runs puppet apply to setup Puppet Master
* runs puppet agent to do a second pass and verify installation is usable

.. note:: Puppet manifests take data (passwords, keys or configuration
  parameters) from hiera configuration. To work with our predefined test data
  script links ``hiera/common-example.yaml`` file to
  ``/var/lib/hiera/common.yaml``.  This step must be done before running
  ``bin/install_puppet_master.sh``.

Once done, you can start deploying other nodes.

Nodes and Roles
~~~~~~~~~~~~~~~

Currently, we define server roles via our hiera configuration (ssh://review.fuel-infra.org:29418/fuel-infra/puppet-manifests) using facter value ``ROLE``. Several roles are defined in ``hiera/roles``:

* anon_stat.yaml
* gerrit.yaml
* glusterfs_testing.yaml
* jenkins_master.yaml
* jenkins_slave.yaml
* lab.yaml
* mongo_testing.yaml
* nailgun_demo.yaml
* puppetmaster.yaml
* seed.yaml
* tools.yaml
* tracker.yaml
* web.yaml
* zbxproxy.yaml
* zbxserver.yaml
* znc.yaml

The most of roles are self explainable.

Generic Node Installation
~~~~~~~~~~~~~~~~~~~~~~~~~

Follow these steps to deploy chosen node:

* install base Ubuntu 14.04
* install puppetlabs agent package
* append to ``/etc/hosts`` - ``<Puppet Master IP> puppet pxetool.test.local``
* run ``FACTER_ROLE=<role name> puppet agent --test`` to apply configuration

Jenkins
-------

Our Jenkins instances are configured to run in master-slave mode. We have
Jenkins master instance on a virtual machine and a number of hardware nodes
working as Jenkins slaves.

Jenkins slaves setup
~~~~~~~~~~~~~~~~~~~~

There are several ways to setup Jenkins master-slave connection, and we use two
of them. The first one is organized simply by putting Jenkins master SSH-key in
authorized_keys file for jenkins user on a slave machine. Then you go to the
Jenkins Web UI and create node manually by specifying node IP address. Jenkins
master connects to the slave via SSH, downloads slave.jar file and runs jenkins
process on a slave.

The second approach requires more configuration steps to take, but allows you to
create slave node automatically from a slave node itself. To use it you need:

* install Swarm Plugin on Jenkins master
* create Jenkins user with ability to create nodes
* install jenkins-swarm-slave package on the slave
* configure the slave to use the mentioned Jenkins user
* run jenkins-swarm-slave service on the slave

Service will automatically connect to Jenkins master and create a node with proper
name and IP address.

Though this approach seems to be complicated, it is quite easy to implement it
with Puppet, as we do in jenkins::slave Puppet class (defined in
puppet-manifests/modules/jenkins/manifests/slave.pp).

If you use Gerrit slave with HTTPs support (default hiera value), please also
include jenkins::swarm_slave as it will trust Jenkins Master certificate on
Node side.

The downside of the swarm slave plugin is that every time you reboot Jenkins
master instance, slaves are recreated and, therefore, lose all the labels
assigned to them via Jenkins WebUI.

Jenkins Jobs
------------

Our CI requires many jobs and configuration, it is not convenient to configure
everything with jenkins GUI. We use dedicated `repository <https://github.com/fuel-infra/jenkins-jobs>`_
and `JJB <http://docs.openstack.org/infra/jenkins-job-builder/>`_ to store and manage our jobs.

Install Jenkins Job Builder
~~~~~~~~~~~~~~~~~~~~~~~~~~~

To begin work with jenkins job builder we need to install it and configure.

#. Download git repository and install JJB

   ::

    git clone https://github.com/fuel-infra/jenkins-jobs.git
    virtualenv --system-site-packages venv-jjb
    source venv-jjb/bin/activate
    pip install -r jenkins-jobs/conf/requirements.txt

#. Create file jenkins_jobs.ini with JJB configuration

   ::

    [jenkins]
    user=<JENKINS USER>
    password=<JENKINS PASSWORD>
    url=https://<JENKINS URL>/

    [job_builder]
    ignore_cache=True
    keep_descriptions=False
    recursive=True
    include_path=.:scripts

Upload jobs to Jenkins
~~~~~~~~~~~~~~~~~~~~~~

When we have JJB installed and configured we can upload jobs to jenkins master.
We can upload all jobs configured for one specified server, for example upload of fule-ci can be done in this way:

   ::

     cd jenkins-jobs
     ../venv-jjb/bin/jenkins-jobs --conf ../jenkins_jobs.ini update servers/fuel-ci:common

We can also upload only one selected job

   ::

     cd jenkins-jobs
     ../venv-jjb/bin/jenkins-jobs --conf ../jenkins_jobs.ini update servers/fuel-ci/8.0/community.all.yaml:common

Building ISO with Jenkins
-------------------------

Requirements
~~~~~~~~~~~~

For minimal environment we need 3 systems:

* Jenkins master
* Jenkins slave with enabled slave function for ISO building and BVT testing, hiera example:

   ::

    ---
    classes:
      - '::fuel_project::jenkins::slave'

    fuel_project::jenkins::slave::run_test: true
    fuel_project::jenkins::slave::build_fuel_iso: true

* Seed server used to store builded ISO

Every slave which will be used for ISO testing, like BVT, requires preparation. After puppet installation
and configuration in jenkins master you need to execute on it job prepare_env.
When you build ISO for version newer then 6.1 default parameters are ok, for older versions you need to
select update_devops_2_5_x option.

Create Jenkins jobs
~~~~~~~~~~~~~~~~~~~

To build your own ISO you need to create job configurations for it, it requires a few steps:

#. Create your own jobs repository, for start we will use fuel-ci jobs

   ::

     cd jenkins-jobs/servers
     cp -pr fuel-ci test-ci

#. To build and test ISO we will use files:

   * servers/test-ci/8.0/community.all.yaml
   * servers/test-ci/8.0/fuel_community_publish_iso.yaml
   * servers/test-ci/8.0/fuel_community.centos.bvt_2.yaml
   * servers/test-ci/8.0/fuel_community.ubuntu.bvt_2.yaml

#. In all files you need to make changes:

   * Change email devops+alert@mirantis.com to your own

   * If you don't need reporting jobs you should delete triggering of fuel_community_build_reports in all jobs

    ::

     - job:
        ...
        publishers:
           ...
           - trigger-parameterized-builds:
             ...
             - project: fuel_community_build_reports

   * Update seed name server in file servers/test-ci/8.0/fuel_community_publish_iso.yaml

    ::

     - job:
        ...
        publishers:
           ...
           - trigger-parameterized-builds:
             ...
             - project:  8.0.fuel_community.centos.bvt_2, 8.0.fuel_community.ubuntu.bvt_2
                ...
                predefined-parameters: |
                   ISO_TORRENT=http://seed.fuel-infra.org/fuelweb-iso/fuel-community-$ISO_ID.iso.torrent

   * Update seed name server in file servers/test-ci/8.0/builders/publish_fuel_community_iso.sh

    ::

      sed -i 's/seed-us1.fuel-infra.org/seed.test.local/g' servers/test-ci/8.0/builders/publish_fuel_community_iso.sh
      sed -i 's/seed-cz1.fuel-infra.org/seed.test.local/g' servers/test-ci/8.0/builders/publish_fuel_community_iso.sh

#. Create jobs on jenkins master

   ::

     cd jenkins-jobs
     ../venv-jjb/bin/jenkins-jobs --conf ../jenkins_jobs.ini update servers/test-ci/8.0/community.all.yaml:common
     ../venv-jjb/bin/jenkins-jobs --conf ../jenkins_jobs.ini update servers/test-ci/8.0/fuel_community_publish_iso.yaml:common
     ../venv-jjb/bin/jenkins-jobs --conf ../jenkins_jobs.ini update servers/test-ci/8.0/fuel_community.centos.bvt_2.yaml:common
     ../venv-jjb/bin/jenkins-jobs --conf ../jenkins_jobs.ini update servers/test-ci/8.0/fuel_community.ubuntu.bvt_2.yaml:common

Start ISO building
~~~~~~~~~~~~~~~~~~

When you finish on jenkins master should be created project with name 8.0-community.all, to start
ISO build you need to run it. Build and test procedure have 3 steps:

* ISO building (8.0-community.all)
* when ISO is successfully created it will be uploaded to seed server (8.0.publish_fuel_community_iso)
* successful upload will start BVT test (8.0.fuel_community.centos.bvt_2 and 8.0.fuel_community.ubuntu.bvt_2)


Gerrit
------

Although fuel-* repositories are hosted by the `OpenStack Gerrit <http://review.openstack.org>`_,
we use additional Gerrit instance to host OpenStack packages, internal projects and all the code
related to Infrastructure itself.

Our Gerrit instance is installed and configured by Puppet, including specifying
the exact Java WAR file that is used(link). To manage Gerrit instance we use
`Jeepyb <http://docs.openstack.org/infra/system-config/jeepyb.html>`_ - the tool written by Openstack Infra
team, which allows to store projects configuration in YAML format.

To use Jeepyb with gerrit you need to create "projects.yaml" configuration file,
where for each project you add the following information:

* project name
* project description
* project ACL
* project upstream

If "upstream" option is specified, Jeepyb will automaticaly import the upstream
repository to this new project. To apply the configuration, use "manage-projects" command.

Every project has ACL file. One ACL file can be reused in several projects. In
ACL file, access rights are defined based on the Gerrit user groups.
For example, in this file you can allow certain group to use the Code-Review
+/-2 marks.

In our gerrit, we have some global projects - <projects>/. The Core Reviewers
for these projects are <one-core-group>.

Contributing
~~~~~~~~~~~~

Feedback
~~~~~~~~
