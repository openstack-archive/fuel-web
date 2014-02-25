Fuel Architecture
=================

Master node is the main part of the Fuel project. It contains all the
services needed for network booting of other managed nodes, installing
an operating system and then deploying OpenStack services to create a
cloud environment. Nailgun is the most important service. It's a REST
application written in Python that contains all the business logic of
the system. A user can interact with it either using the Fuel Web
interface or by the means of CLI utility. He can create environment,
edit its settings, assign roles to the doscovered nodes and start the
deployment process of the new OpenStack cluster.

Nailgun stores all its data in the PostgreSQL database. It contains
the hardware configuration of all discovered managed nodes, the roles,
environment settings and the status of the provisioning and the
deployment processes.

.. uml::

    package "Discovered Node" {
      component "Nailgun Agent"
    }

    package "Master Node" {
      component "Nailgun"
      component "Database"
      interface "REST API"
      component "Fuel Web"
    }

    actor "User"
    component "CLI tool"

    [User] -> [CLI tool]
    [User] -> [Fuel Web]
    [Nailgun Agent] -> [REST API] : Upload hardware profile

    [CLI tool] -> [REST API]
    [Fuel Web] -> [REST API]
    [REST API] -> [Nailgun]
    [Nailgun] -> [Database]

Managed nodes are added using a special bootstrap image and the PXE
boot server located on the master node. The bootstrap image runs
the Nailgun agent. It's a speciall script that collects the server's
hardware information and submits it to the Nailgun through the REST API
too.

The deployment process is started by the user after he have configured
a new environment. Nailgun service creates a JSON file with the
environment settings, its nodes and their roles and puts this
file into the RabbitMQ queue. This message should be recived by one of
the Astute workers who will actually deploy the environment.

.. uml::
    package "Master Node" {
      component "Nailgun"
      interface "RabbitMQ"

      package "Naily Worker" {
        component Naily
        component Astute
      }

      component "Cobbler"
      component "DHCP and TFTP"
    }

    [Nailgun] <-> [RabbitMQ] : Put task into Nailgun queue
    [Naily] <-> [RabbitMQ] : Take task from Nailgun queue
    [Naily] -> [Astute]
    [Astute] -> [Cobbler] : Set node's settings through XML-RPC
    [Cobbler] -> [DHCP and TFTP]

Naily worker is listening the RabbitMQ queue and recives the message.
It uses Astute library that implements all deployment actions.
First it starts the provisioning of the environment's nodes. Astute uses
XML-RPC to set these nodes configuration in Cobbler and then reboots the
nodes using MCollective agent to let the Cobbler to install their
operating systems. Cobbler is the deployment system that can control
DHCP and TFTP services and use them to network boot the managed node
and start the OS installer with the given settings.

Astute puts the special message into the RabbitMQ queue that contains
the action that should be executed on the managed node. MCollective
servers are started on all bootstraped nodes and they always listen to
these messages and when they recive them they run the required agent's
action with given parameters. MCollective agents are just a Ruby files
with a set of procedures. These procedures are actions that the server
can run.

When the managed node's OS is installed Astute can start the deployment
of OpenStack services. First it uploads this node's configuration
to the */etc/astute.yaml* file on node using the *uploadfile* agent.
This file contains all the variables and settings that would be needed
for the deployment.

Then Astute uses *puppetsync* agent to synchronize
the Puppet modules and manifests. This agent runs the rsync process that
connects to the rsyncd server on the master node and downloads the
latest version of Puppet modules and manifests.

.. uml::
    package "Master Node" {
      interface "RabbitMQ"
      component "Rsyncd"
      component "Astute"
    }

    package "Managed Node" {
      interface "MCollective"
      package "MCollective Agents" {
        component "uploadfile"
        component "puppetsync"
        component "puppetd"
        component "shell"
      }
      component "Puppet"
      component "Rsync"
      interface "astute.yaml"
      component "Puppet Modules"
    }

    [Astute] <-> [RabbitMQ]
    [RabbitMQ] <-> [MCollective]

    [MCollective] -> [uploadfile]
    [MCollective] -> [puppetsync]
    [MCollective] -> [puppetd]
    [MCollective] -> [shell]

    [uploadfile] ..> [astute.yaml]
    [puppetsync] -> [Rsync]
    [puppetd] -> [Puppet]
    [Rsync] <..> [Rsyncd]

    [Rsync] ..> [Puppet Modules]
    [astute.yaml] ..> [Puppet]
    [Puppet Modules] ..> [Puppet]

When the modules are synchronized Astute can run the actual deployment
by applying the main Puppet manifest *site.pp*. Mcollective agent runs
the Puppet process in the background using the *daemonize* tool and
Astute periodically poll the agent to check if the deployment have
finished and report the progress to the Nailgun through its RabbitMQ
queue.

When started Puppet reads the *astute.yaml* file content as a fact and
then parses it into the *$fuel_settings* structure used to get all
deployment settings from.

When the Puppet process exits either successfully or with an error
Astute gets the summary file from the node and reports the results to
the Nailgun. The user can always monitor both the progress and the
results using Fuel Web interface or the CLI tool.

Astute also does some more actions depending on environment
configuration either before the deployment of after successful one.

* Generates and uploads SSH keys that will be needed during deployment.
* Uploads CirrOS image into Glance after the deployment.
* Updates */etc/hosts* file when on all nodes when the new one is added.
* Updates RadosGW map when the Ceph nodes are deployed.

Astute also uses MCollective agents when a node or the entire
environment is being removed. It erases all boot sectors on the node
and reboots it. The node will be network booted with the bootstrap
image again and becomes ready to be used in a new environment.
