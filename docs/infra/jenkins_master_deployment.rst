Jenkins Master
==============

Jenkins master as a head of CI systems handles all tasks related to the build
system, being responsible for its slaves connectivity, users authentication
and job launches.

Deployment
----------

To deploy Jenkins master it is required to have Puppet Master already deployed
and already working DNS solution. Also please consider using Hiera role when
deploying Jenkins Master. As an example see the ``jenkins_master`` role, which
is included in ``fuel-infra/puppet-manifests`` repository.

#. Ensure in jenkins master hiera role to have the following parameters are
   set:

   .. code-block:: ini

     ---
     classes:
        - '::fuel_project::jenkins::master'

     jenkins::master::jenkins_ssh_private_key_contents: |
       -----BEGIN RSA PRIVATE KEY-----
       MIIEogIBAAKCAQEAzVoDH+iIrEmNBytJqR5IFYUcR7A6JvNTyelt4wIHEgVmNSs/
       9ry/fEivdaaYGJpw2tri23IWNl5PXInnzKZu0KuRDuqEjyiSYQA8gmAF/+2KJmSM
       uF7ux8RIdGelQi7dA8psDeLQUvSbkyErxJtewS4LYrPwHpgNnkSJdCQHT3/a5kKb
       OCj+QIRutLnHbUyg9MvExSveWrXqZYHKvSS0SJ4a3YP75yS2yp1e5T9YOXX2Na5u
       m7puz/icH9rXUzmtG+bnCv/ollW8jzuGdmnz6W5YeFcp33tsDM86RgKd5+TMLR9h
       GZkl5vwevwpIDhUTrJlh/DM0BLzQRh4cPjjUfQIDAQABAoIBAGQO0OjyR+4S5Imy
       uPCTlbIOqunvX1ZtR81hVS7AZSuNv/B2Q3N5IqBvVjcwVnneftDUyKb+nv4c0/SW
       KYEZM3OvtT2cXbzXmwNytwkburCqUJ9GbR7E+voRlPBLNEXcScq4DhByDOnu0ANP
       rWDeB7x/MAMHBCAUHMaaRJN3nqxIEvvzKK0B3GpRsVgGLDTQ4wX9ojmPQ7H8QQVV
       ZnfiJxhXoXbcQUudwn2etMOQpnOzq+fUSj2U6U+pxnkQBcdb2TUqLVOdKqzV4Xwc
       u/mqmtMRb6cjRpH+J1ajZqgbn6yw756TmP/LT5Jb0l/tI4b/HrPlXuXSJHtLFvQE
       D00tK+ECgYEA+Gk447CteVDmkKU/kvDh9PVbZRsuF24w+LK6VLLxSp94gGIlHyNN
       WdamBZviBIOnyz8x3WPd8u2LnkBla7L4iJgh/v5XgAK4I5ES94VGiEnEWJDXVKOY
       JW9mRH7CElmhRbhVuMQoEDonhiLNLnRwwwjF79dSlANpJxioMCVOMkUCgYEA06AH
       sx5gzdCt1OAgR2XPANMLdOgufjWsQiZtCIlLQTxzEjmF3uwsWy+ugVQIFZnwIUxw
       5O41uDji1lwE/ond15oBMFB97unzsgFW3uHSV7yWJv1SVP7LSXZnBIRhwqsozYNL
       3py9k/EvuZ4P+EoR8F3COC5gg62qxO5L2P3O2NkCgYAJ+e/W9RmCbcVUuc470IDC
       nbf174mCV2KQGl1xWV5naNAmF8r13S0WFpDEWOZS2Ba9CuStx3z6bJ/W0y8/jAh/
       M9zpqL1K3tEWXJUua6PRhWTlSavcMlXB6x9oUM7qfb8EVcrbiMUzIaLEuFEVNIfy
       zT9lynf+icSHVW4rwNPLIQKBgCJ0VYyWD5Cyvvp/mwHE05UAx0a7XoZx2p/SfcH8
       CGKQovN+pgsLTJV0B+dKdR5/N5dUSLUdC2X47QWVacK/U3z8t+DT2g0BzglXKnuT
       LJnYPGIQsEziRtqpClCz9O6qyzPagom13y+s/uYrk9IKzSzjNvHKqzAFIF57paGo
       gPrRAoGAClmcMYF4m48mnMAj5htFQg1UlE8abKygoWRZO/+0uh9BrZeQ3jsWnUWW
       3TWXEjB/RazdPB0PWfc3kjruz8IhDsLKQYPX+h8JuLO8ZL20Mxo7o3bs/GQnDrw1
       g/PCKBJscu0RQxsa16tt5aX/IM82cJR6At3tTUyUpiwqNsVClJs=
       -----END RSA PRIVATE KEY-----

     jenkins::master::jenkins_ssh_public_key_contents: |
       'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDNWgMf6IisSY0HK0mpHkgVhRxHs \
       Dom81PJ6W3jAgcSBWY1Kz/2vL98SK91ppgYmnDa2uLbchY2Xk9ciefMpm7Qq5EO6oS \
       PKJJhADyCYAX/7YomZIy4Xu7HxEh0Z6VCLt0DymwN4tBS9JuTISvEm17BLgtis/Aem \
       A2eRIl0JAdPf9rmQps4KP5AhG60ucdtTKD0y8TFK95ateplgcq9JLRInhrdg/vnJLb \
       KnV7lP1g5dfY1rm6bum7P+Jwf2tdTOa0b5ucK/+iWVbyPO4Z2afPpblh4Vynfe2wMz \
       zpGAp3n5MwtH2EZmSXm/B6/CkgOFROsmWH8MzQEvNBGHhw+ONR9'

#. Set proper service FQDN of your jenkins master instance:

   .. code-block:: ini

     fuel_project::jenkins::master::service_fqdn: 'puppet-master.test.local'

#. Adjust the security model of your jenkins after the deployment:

   .. code-block:: ini

     jenkins::master::security_model: 'unsecured' || 'password' || 'ldap'

.. note::
   The ``password`` is the most basic one, when Jenkins has no access to
   the LDAP and you still require some authorization to be enabled in the
   Jenkins.

To deploy Jenkins master, complete the following steps:

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

The last action requests the client's certificate, which has to be signed from
the Puppet Master, in order to continue the puppet run.