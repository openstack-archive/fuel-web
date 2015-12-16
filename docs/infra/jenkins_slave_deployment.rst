Jenkins Slave
=============

The Jenkins Slave is a machine that is set up to run build projects scheduled
from the master. Slave runs a dedicated program called a "slave agent"
spawned from the master, thus there is no need to install Jenkins itself
on a slave.

--------
Overview
--------

------------------------
Jenkins Slave deployment
------------------------

There are few ways to setup Jenkins master-slave connection, however in our
infra currently we use only one of them.
In general, the Jenkins master SSH-key is to be placed in authorized_keys file
for the jenkins user on a slave machine. Then via the Jenkins Master's WebUI
create a node manually by specifying slave's node FQDN. After, the Jenkins
master will connect to the slave via SSH to the jenkins user, upload
'slave.jar' file and spawn it on slave using jenkins user.

In order to deploy Jenkins Slave please choose an already existing hiera
role for a specific jenkins instance or create a new one. For instance you
can use 'jenkins_slave' role as a base start.








