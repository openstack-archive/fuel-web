Fuel Architecture
=================

Good overview of Fuel architecture is represented on
`OpenStack wiki <https://wiki.openstack.org/wiki/Fuel#Fuel_architecture>`_.
You can find a detailed breakdown of how this works in the
:doc:`Sequence Diagrams </develop/sequence>`.

Master node is the main part of the Fuel project. It contains all the
services needed for network provisioning of other managed nodes,
installing an operating system, and then deploying OpenStack services to
create a cloud environment. *Nailgun* is the most important service.
It is a RESTful application written in Python that contains all the
business logic of the system. A user can interact with it either using
the *Fuel Web* interface or by the means of *CLI utility*. He can create
a new environment, edit its settings, assign roles to the discovered
nodes, and start the deployment process of the new OpenStack cluster.

Nailgun stores all of its data in a *PostgreSQL* database. It contains
the hardware configuration of all discovered managed nodes, the roles,
environment settings, current deployment status and progress of
running deployments.

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

Managed nodes are discovered over PXE using a special bootstrap image
and the PXE boot server located on the master node. The bootstrap image
runs a special script called Nailgun agent. The agent **nailgun-agent.rb**
collects the server's hardware information and submits it to Nailgun
through the REST API.

The deployment process is started by the user after he has configured
a new environment. The Nailgun service creates a JSON data structure
with the environment settings, its nodes and their roles and puts this
file into the *RabbitMQ* queue. This message should be received by one
of the worker processes who will actually deploy the environment. These
processes are called *Astute*.

.. uml::
    package "Master Node" {
      component "Nailgun"
      interface "RabbitMQ"

      package "Astute Worker" {
        component Astute
      }

      component "Cobbler"
      component "DHCP and TFTP"
    }

    [Nailgun] -> [RabbitMQ] : Put task into Nailgun queue
    [Astute] <- [RabbitMQ] : Take task from Nailgun queue
    [Astute] -> [Cobbler] : Set node's settings through XML-RPC
    [Cobbler] -> [DHCP and TFTP]

The Astute workers are listening to the RabbitMQ queue and receives
messages. They use the *Astute* library which implements all deployment
actions. First, it starts the provisioning of the environment's nodes.
Astute uses XML-RPC to set these nodes' configuration in Cobbler and
then reboots the nodes using *MCollective agent* to let Cobbler install
the base operating system. *Cobbler* is a deployment system that can
control DHCP and TFTP services and use them to network boot the managed
node and start the OS installer with the user-configured settings.

Astute puts a special message into the RabbitMQ queue that contains
the action that should be executed on the managed node. MCollective
servers are started on all bootstrapped nodes and they constantly listen
for these messages, when they receive a message, they run the required
agent action with the given parameters. MCollective agents are just Ruby
scripts with a set of procedures. These procedures are actions that the
MCollective server can run when asked to.

When the managed node's OS is installed, Astute can start the deployment
of OpenStack services. First, it uploads the node's configuration
to the **/etc/astute.yaml** file on node using the **uploadfile** agent.
This file contains all the variables and settings that will be needed
for the deployment.

Next, Astute uses the **puppetsync** agent to synchronize Puppet
modules and manifests. This agent runs an rsync process that connects
to the rsyncd server on the Master node and downloads the latest version
of Puppet modules and manifests.

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

When the modules are synchronized, Astute can run the actual deployment
by applying the main Puppet manifest **site.pp**. MCollective agent runs
the Puppet process in the background using the **daemonize** tool.
The command looks like this:
::

  daemonize puppet apply /etc/puppet/manifests/site.pp"

Astute periodically polls the agent to check if the deployment has
finished and reports the progress to Nailgun through its RabbitMQ queue.

When started, Puppet reads the **astute.yaml** file content as a fact
and then parses it into the **$fuel_settings** structure used to get all
deployment settings.

When the Puppet process exits either successfully or with an error,
Astute gets the summary file from the node and reports the results to
Nailgun. The user can always monitor both the progress and the
results using Fuel Web interface or the CLI tool.

Fuel installs the **puppet-pull** script. Developers can use it if
they need to manually synchronize manifests from the Master node and
run the Puppet process on node again.

Astute also does some additional actions, depending on environment
configuration, either before the deployment of after successful one.

* Generates and uploads SSH keys that will be needed during deployment.
* During network verification phase **net_verify.py** script.
* Uploads CirrOS guest image into Glance after the deployment.
* Updates **/etc/hosts** file on all nodes when new nodes are deployed.
* Updates RadosGW map when Ceph nodes are deployed.

Astute also uses MCollective agents when a node or the entire
environment is being removed. It erases all boot sectors on the node
and reboots it. The node will be network booted with the bootstrap
image again, and will be ready to be used in a new environment.
