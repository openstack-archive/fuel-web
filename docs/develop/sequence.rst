Sequence Diagrams
=================

OS Provisioning
---------------
 .. uml::
    title Nodes Provisioning
    actor WebUser

    box "Physical Server"
        participant NodePXE
        participant NodeAgent
    end box

    NodePXE -> Cobbler: PXE discovery
    Cobbler --> NodePXE: bootstrap OS image
    NodePXE -> Cobbler: network settings request
    Cobbler --> NodePXE: IP, DNS response
    NodePXE -> NodePXE: OS installation
    NodePXE -> NodeAgent: starts agent
    NodePXE -> MC: starts MCollective
    NodeAgent -> Ohai: get info
    Ohai --> NodeAgent: info
    NodeAgent -> NodePXE: get admin node IP
    NodePXE --> NodeAgent: admin node IP
    NodeAgent -> Nailgun: Registration
    |||
    WebUser -> Nailgun: create cluster
    WebUser -> Nailgun: add nodes to cluster
    WebUser -> Nailgun: deploy cluster
    |||
    Nailgun -> Astute: Provision CentOS
    Astute -> Cobbler: Provision CentOS
    Cobbler -> NodePXE: ssh to reboot
    Cobbler --> NodePXE: CentOS image
    NodePXE -> NodeAgent: starts agent
    NodePXE -> MC: starts MC agent
    NodeAgent -> Nailgun: Node metadata

Networks Verification
---------------------
 .. uml::
    title Network Verification
    actor WebUser

    WebUser -> Nailgun: verify networks (cluster #1)
    Nailgun -> Astute: verify nets (100-120 vlans)
    Astute -> MC: start listeners
    MC -> net_probe.py: forks to listen
    MC --> Astute: listening
    Astute -> MC: send frames
    MC -> net_probe.py: send frames
    net_probe.py --> MC: sent
    MC --> Astute: sent

    Astute -> MC: get result
    MC -> net_probe.py: stop listeners
    net_probe.py --> MC: result
    MC --> Astute: result graph
    Astute --> Nailgun: response vlans Ok
    Nailgun --> WebUser: response


Details on Cluster Provisioning & Deployment (via Facter extension)
-------------------------------------------------------------------
 .. uml::
    title Cluster Deployment
    actor WebUser

    Nailgun -> Astute: Provision,Deploy
    Astute -> MC: Type of nodes?
    MC -> Astute: bootstrap
    Astute -> Cobbler: create system,reboot
    Astute -> MC: Type of nodes?

    MC --> Astute: booted in target OS
    Astute --> Nailgun: provisioned
    Nailgun --> WebUser: status on UI
    Astute -> MC: Create /etc/astute.yaml

    Astute -> MC: run puppet
    MC -> Puppet: runonce
    Puppet -> Facter: get facts
    Facter --> Puppet: set facts and parse astute.yaml

    Puppet -> Puppet: applies $role
    Puppet --> MC: done
    MC --> Astute: deploy is done
    Astute --> Nailgun: deploy is done
    Nailgun --> WebUser: deploy is done

Once deploy and provisioning messages are accepted by Astute, provisioning
method is called.  Provisioning part creates system in Cobbler and
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
