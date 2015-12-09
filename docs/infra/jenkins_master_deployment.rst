Jenkins Master
==============

Overview
--------

Jenkins master as a head of CI systems handles all tasks related to the build system, being responsible
for its slaves connectivity, users authentication and job launches.

Deployment
----------

To deploy Jenkins master it is required to have Puppet Master already deployed
and already working DNS solution. Also please consider using Hiera role when
deploying Jenkins Master. As an example see the 'jenkins_master' role, which
is included in fuel-infra/puppet-manifests repository.

#. Install base Ubuntu 14.04 with SSH service and set appropriate FQDN.

#. Install puppet agent package.

   ::

     # apt-get update; apt-get install -y puppet

#. Enable puppet agent.

   ::

     # puppet agent --enable

#. Run the Jenkins Master deployment.

   ::

     # FACTER_ROLE=jenkins_master FACTER_LOCATION=us1 puppet agent -tvd \
     # --server puppet-master.test.local --waitforcert 60

The last action will requests the certificate from Puppet Master first, on which
the signing of the client's certificate must be completed, in order to continue
the puppet run.
