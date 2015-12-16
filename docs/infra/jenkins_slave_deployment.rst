Jenkins Slave
=============

The Jenkins Slave is a machine that is set up to run build projects scheduled
from the master. Slave runs a dedicated program called a ``slave agent``
spawned from the master, thus there is no need to install Jenkins itself
on a slave.

Deployment
----------

There are few ways to setup Jenkins master-slave connection, however in our
infra currently we use only one of them.
In general, the Jenkins master SSH-key is to be placed in authorized_keys file
for the jenkins user on a slave machine. Then via the Jenkins Master's WebUI
create a node manually by specifying slave's node FQDN. After, the Jenkins
master will connect to the slave via SSH to the jenkins user, upload
``slave.jar`` file and spawn it on slave using jenkins user.

In order to deploy Jenkins Slave please look at already existing hiera
role for an example of jenkins slave instance. Check if ssh public key
authentication is properly configured.

#. Ensure that in jenkins master hiera role the following two parameters are
   set:

   .. code-block:: ini

     ---
     classes:
        - '::fuel_project::jenkins::master'

     jenkins::master::jenkins_ssh_private_key_contents: |
       -----BEGIN RSA PRIVATE KEY-----
       MIIEogIBAAKCAQEAzVoDH+iIrEmNBytJqR5IFYUcR7A6JvNTyelt4wIHEgVmNSs/
       9ry/fEivdaaYGJpw2tri23IWNl5PXInnzKZu0KuRDuqEjyiSYQA8gmAF/+2KJmSM
       ...
       3TWXEjB/RazdPB0PWfc3kjruz8IhDsLKQYPX+h8JuLO8ZL20Mxo7o3bs/GQnDrw1
       g/PCKBJscu0RQxsa16tt5aX/IM82cJR6At3tTUyUpiwqNsVClJs=
       -----END RSA PRIVATE KEY-----

     jenkins::master::jenkins_ssh_public_key_contents: |
       'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDNWgMf6IisSY0HK0mpHkgVhRxHs \
       Dom81PJ6W3jAgcSBWY1Kz/2vL98SK91ppgYmnDa2uLbchY2Xk9ciefMpm7Qq5EO6oS \
       ...
       KnV7lP1g5dfY1rm6bum7P+Jwf2tdTOa0b5ucK/+iWVbyPO4Z2afPpblh4Vynfe2wMz \
       zpGAp3n5MwtH2EZmSXm/B6/CkgOFROsmWH8MzQEvNBGHhw+ONR9'


#. In the jenkins slave role ensure to set proper 'authorized_keys' parameter

   .. code-block:: ini

     ---
     classes:
       - fuel_project::jenkins::slave

     jenkins::slave::authorized_keys:
       'jenkins@jenkins-master.test.local':
         type: ssh-rsa
         key: 'AAAAB3NzaC1yc2EAAAADAQABAAABAQDNWgMf6IisSY...BGHhw+ONR9'

     # optional - if you wish to use also password authentication, set to true:
     ssh::sshd::password_authentication: true

The above configuration is mandatory to be set in order to get proper
master-to-slave connection.

Other case, if the slaves running the particular hiera role are suppose to be
able to buid the ISO, it is required to enable 'build_fuel_iso' parameter in
the 'slave' class.

   .. code-block:: ini

     fuel_project::jenkins::slave::build_fuel_iso: true

To deploy Jenkins slave, complete the following steps:

#. Install base Ubuntu 14.04 with SSH service and set appropriate FQDN.

#. Install puppet agent package:

   .. code-block:: console

     apt-get update; apt-get install -y puppet

#. Enable puppet agent:

   .. code-block:: console

     puppet agent --enable

#. Run the Jenkins Master deployment.

   .. code-block:: console

     FACTER_ROLE=jenkins_slave FACTER_LOCATION=us1 puppet agent -tvd \
     --server puppet-master.test.local --waitforcert 60

The last action requests the client's certificate. To continue the puppet run,
the certificate should be signed from the Puppet Master.