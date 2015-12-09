Jenkins Master
==============

Jenkins master as a head of CI systems handles all tasks related to the build
system being responsible for its slaves connectivity, users authentication, and
job launches.

Deployment
----------

Before you deploy the Jenkins master, perform the following tasks:
#. Verify that the Puppet Master is deployed and DNS solution is working.
#. Consider using the Hiera role. As an example, see the ``jenkins_master`` role included in the ``fuel-infra/puppet-manifests`` repository.
#. Set the following parameters for the Hiera role on the Jenkins Master:

   .. code-block:: ini

     ---
     classes:
        - '::fuel_project::jenkins::master'

     jenkins::master::jenkins_ssh_private_key_contents: |
       -----BEGIN RSA PRIVATE KEY-----
       MIIEogIBAAKCAQEAzVoDH+iIrEmNBytJqR5IFYUcR7A6JvNTyelt4wIHEgVmNSs/
       9ry/fEivdaaYGJpw2tri23IWNl5PXInnzKZu0KuRDuqEjyiSYQA8gmAF/+2KJmSM
       OCj+QIRutLnHbUyg9MvExSveWrXqZYHKvSS0SJ4a3YP75yS2yp1e5T9YOXX2Na5u
       ...
       LJnYPGIQsEziRtqpClCz9O6qyzPagom13y+s/uYrk9IKzSzjNvHKqzAFIF57paGo
       3TWXEjB/RazdPB0PWfc3kjruz8IhDsLKQYPX+h8JuLO8ZL20Mxo7o3bs/GQnDrw1
       g/PCKBJscu0RQxsa16tt5aX/IM82cJR6At3tTUyUpiwqNsVClJs=
       -----END RSA PRIVATE KEY-----

     jenkins::master::jenkins_ssh_public_key_contents: |
       'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDNWgMf6IisSY0HK0mpHkgVhRxHs
       Dom81PJ6W3jAgcSBWY1Kz/2vL98SK91ppgYmnDa2uLbchY2Xk9ciefMpm7Qq5EO6oS \
       ...
       KnV7lP1g5dfY1rm6bum7P+Jwf2tdTOa0b5ucK/+iWVbyPO4Z2afPpblh4Vynfe2wMz \
       zpGAp3n5MwtH2EZmSXm/B6/CkgOFROsmWH8MzQEvNBGHhw+ONR9'

#. Set proper service FQDN of the Jenkins Master instance:

   .. code-block:: ini

     fuel_project::jenkins::master::service_fqdn: 'jenkins-master.test.local'

#. Adjust the security model of the Jenkins after the deployment:

   .. code-block:: ini

     jenkins::master::security_model: 'unsecured' || 'password' || 'ldap'

   .. note::
      The ``password`` is the most basic one, when Jenkins has no access to
      the LDAP and you still require some authorization to be enabled in the
      Jenkins.

To deploy the Jenkins Master, complete the following steps:

#. Install base Ubuntu 14.04 with SSH service and set appropriate FQDN.

#. Install puppet agent package:

   .. code-block:: console

     apt-get update; apt-get install -y puppet

#. Enable puppet agent:

   .. code-block:: console

     puppet agent --enable

#. Run the Jenkins Master deployment:

   .. code-block:: console

     FACTER_ROLE=jenkins_master FACTER_LOCATION=us1 puppet agent -tvd \
     --server puppet-master.test.local --waitforcert 60

The last action requests the client's certificate. To continue the puppet run,
the certificate should be signed from the Puppet Master.