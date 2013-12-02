Sequence Diagrams
=================

OS Provisioning
---------------
.. image:: /_diagrams/sequence_nodes_provisioning.*

Networks Verification
---------------------
.. image:: /_diagrams/sequence_network_verification.*


Details on Cluster Provisioning & Deployment (via Facter extension)
-------------------------------------------------------------------
.. image:: /_diagrams/sequence_cluster_deployment.*

Once deploy and provisioning messages are accepted by Naily, provisioining 
method is called in Astute.  Provisioning part creates system in Cobbler and 
calls reboot over Cobbler. Then Astute uses `MCollective direct addressing 
mode 
<http://www.devco.net/archives/2012/06/19/mcollective-direct-addressing-mode.ph
p>`_
to check if all required nodes are available, include puppet agent on them. If 
some nodes are not yet ready, Astute waits for a few seconds and tries to
request again.  When nodes are booted in target OS, Astute uses upload_file 
MCollective plugin to push data to a special file */etc/astute.yaml* on the 
target system.
Data include role and all other variables needed for deployment. Then, Astute 
calls puppetd MCollective plugin to start deployment. Puppet is started on 
nodes.

Accordingly, puppet agent starts its run. Modules contain facter extension, 
which runs before deployment. Extension reads data from */etc/astute.yaml* 
placed by mcollective, and extends Facter data with it as a single fact, which 
is then parsed by *parseyaml* function to create *$::fuel_settings* data 
structure. This structure contains all variables as a single hash and
supports embedding of other rich structures such as nodes hash or arrays.
Case structure in running class chooses appropriate class to import,
based on *role* and *deployment_mode* variables found in */etc/astute.yaml*.
