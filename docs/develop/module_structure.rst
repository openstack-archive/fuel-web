Contributing to Fuel Library
============================

This chapter will explain how to add new module or project into Fuel Library, 
how to integrate with other components
and how to avoid different problems and potential mistakes. Fuel Library is a 
very big project and even experienced Puppet user will have problems 
understanding its structure and internal workings.

Adding new modules to fuel-library
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

*Case A. Pulling in an existing module*

If you are adding a module that is the work of another project and is already
tracked in separate repo then:

1. Create a review request with a unmodified copy of the upstream module from
whichever point you are working from and *no* other related modifications.

* This review should also contain the commit hash from the upstream repo
  in the commit message.
* The review should be evaluated to determine its suitability and either rejected
  (for licensing, code quality, outdated version requested) or accepted
  without requiring modifications.
* The review should not include code that calls this new module.

2.  Any changes necessary to make it work with Fuel should then be proposed
as a dependent change(s).

*Case B. Adding a new module*

If you are adding a new module that is a work purely for Fuel and will not be
tracked in a separate repo then submit incremental reviews that consist of
working implementation of features for your module.

If you have features that are necessary, but do not work fully yet, then prevent
them from running during the deployment. Once your feature is complete, submit
a review to activate the module during deployment.

Contributing to existing fuel-library modules
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

As developers of Puppet modules, we tend to collaborate with the Puppet
OpenStack community. As a result, we contribute to upstream modules all of the
improvements, fixes and customizations we make to improve Fuel as well.
That implies that every contributor must follow Puppet DSL basics,
`puppet-openstack dev docs
<https://wiki.openstack.org/wiki/Puppet-openstack#Developer_documentation>`_
and `Puppet rspec tests
<https://wiki.openstack.org/wiki/Puppet-openstack#Rspec_puppet_tests>`_
requirements.

The most common and general rule is that upstream modules should be modified
only when bugfixes and improvements could benefit everyone in the community.
And appropriate patch should be proposed to the upstream project prior
to Fuel project.

In other cases (like applying some very specific custom logic or settings)
contributor should submit patches to ``openstack::*`` `classes
<https://github.com/stackforge/fuel-library/tree/master/deployment/puppet/
openstack>`_

Fuel library includes custom modules as well as ones forked from upstream
sources. Note that ``Modulefile``, if any exists, should be used in order
to recognize either given module is forked upstream one or not.
In case there is no ``Modulefile`` in module's directory, the contributor may
submit a patch directly to this module in Fuel library.
Otherwise, he or she should submit patch to upstream module first, and once
merged or +2 recieved from a core reviewer, the patch should be backported to
Fuel library as well. Note that the patch submitted for Fuel library should
contain in commit message the upstream commit SHA or link to github pull-request
(if the module is not on stackforge) or Change-Id of gerrit patch.

The Puppet modules structure
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

First let's start with Puppet modules structure. If you want to contribute you 
code into the Fuel Library it should be organized into a Puppet module. Modules
are self-contained sets of Puppet code that usually are made to perform specific 
function. For example you could have a module for every service you are going 
to configure or for every part of your project. Usually it's a good idea to 
make a module independent but sometimes it could require or be required by 
other modules so module can be thinked about as a library.

The most important part of every Puppet module is its **manifests** folder. 
This folder contains Puppet classes and definitions which also contain 
resources managed by this module. Modules and classes also form namespaces. 
Each class or definition should be placed each into single file inside 
manifests folder and this file should be named same as class or definition.
Module should have top level class that serves as a module's entry point and 
is named same as the module. This class should be placed into *init.pp* file.
This example module shows the standard structure every Puppet module should 
follow.::

  example
  example/manifests/init.pp
  example/manifests/params.pp
  example/manifests/client.pp
  example/manifests/server
  example/manifests/server/vhost.pp
  example/manifests/server/service.pp
  example/templates
  example/templates/server.conf.erb
  example/files
  example/files/client.data

The first file in manifests folder is named init.pp and should contain entry 
point class of this module. This class should be named same as our module.::

  class example {

  }

The second file is *params.pp*. These files are not mandatory but are often 
used to store different configuration values and parameters used by other 
classes of the module. For example, it could contain service name and package 
name of our hypothetical example module. There could be conditional statements 
if you need to change default values in different environments. *Params* class 
should be named as child to module's namespace as all other classes of the 
module.::

  class example::params {
    $service = 'example'
    $server_package = 'example-server'
    $client_package = 'example-client'
    $server_port = '80'
  }

All other inside the manifests folder contain classes as well and can
perform any action you might want to identify as a separate piece of code.
This generally falls into sub-classes that don't require its users to
configure the parameters explicitly, or possibly these are simply optional
classes that are not required in all cases. In the following example,
we create a client class to define a client package that will be installed,
placed into a file called *client.pp*.::

  class example::client {
    include example::params

    package { $example::params::client_package :
      ensure => installed,
    }

  }

As you can see we have used package name from params class. Consolidating
all values that might require editing into a single class, as opposed to
hardcoding them, allows you to reduce the effort required to maintain and
develop the module further in the future. If you are going to use any values
from params class you should not forget to include it first to force its
code to execute and create all required variables.

You can add more levels into the namespace structure if you want. Let's create 
server folder inside our manifests folder and add *service.pp* file there. It 
would be responsible for installation and running server part of our imaginary 
software. Placing the class inside subfolder adds one level into name of
contained class.::

  class example::server::service (
    $port = $example::params::server_port,
  ) inherits example::params {

    $package = $example::params::server_package
    $service = $example::params::service

    package { $package :
      ensure => installed,
    }

    service { $service :
      ensure     => running,
      enabled    => true,
      hasstatus  => true,
      hasrestart => true,
    }

    file { 'example_config' :
      ensure  => present,
      path    => '/etc/example.conf',
      owner   => 'root',
      group   => 'root',
      mode    => '0644',
      content => template('example/server.conf.erb'),
    }

    file { 'example_config_dir' :
      ensure => directory,
      path   => '/etc/example.d',
      owner  => 'example',
      group  => 'example',
      mode   => '0755',
    }

    Package[$package] -> File['example_config', 'example_config_dir'] ~> 
      Service['example_config']

  }

This example is a bit more complex. Let's see what it does.

Class *example::server::service* is **parametrized** and can accept one 
parameter - port to which server process should bind to. It also uses a popular 
"smart defaults" hack. This class inherits the params class and uses its values 
default only if no port parameter is provided. In this case, you can't use 
*include params* to load the default values because it's called by the
*inherits example::params* clause of the class definition.

Then inside our class we take several variable from params class and declare 
them as variable of the local scope. This is conveniency hack to make their 
names shorter.

Next we declare our resources. These resources are package, service, config 
file and config dir. Package resource will install package which name is taken 
from variable if it's not already installed. File resources create config file 
and config dir and service resource would start the daemon process and enable 
its autostart.

And the last but not least part of this class is *dependency* declaration. We 
have used "chain" syntax to specify the order of evaluation of these 
resources. Of course it's important first to install package, then 
configuration files and only then start the service. Trying to start service 
before installing package will definitely fail. So we need to tell Puppet that 
there are dependencies between our resources.

The arrow operator that has a tilde instead of a minus sign (~>) means not
only dependency relationship but also *notifies* the object to the right
of the arrow to refresh itself. In our case any changes in configuration
file would make the service to restart and load new configuration file.
Service resource react to notification event by restating managed service.
Other resources may perform different actions instead if they support it.

Ok, but where do we get our configuration file content from? It's generated by 
template function. Templates are text files with Ruby's erb language tags that 
are used to generate needed text file using pre-defined text and some 
variables from manifest.

These template files are located inside the **templates** folder of the
module and usually have *erb* extension. Calling template function with
template name and module name prefix will try to load this template and
compile it using variables from the local scope of the class function was
called from. For example we want to set bind port of our service in its
configuration file so we write template like this and save it inside
templates folder as server.conf.erb file.::

  bind_port = <%= @port %>

Template function will replace 'port' tag with value of port variable from our 
class during Puppet's catalog compilation.

Ok, now we have our service running and client package installed. But what if 
our service needs several virtual hosts? Classes cannot be declared several 
times with different parameters so it's where **definitions** come to the 
rescue. Definitions are very similar to classes, but unlike classes, they
have titles like resources do and can be used many times with different
title to produce many instances of managed resources. Defined types can
also accept parameters like parametrized classes do.

Definitions are placed in single files inside manifests directories same as 
classes and are similarly named using namespace hierarchy.
Let's create our vhost definition.::

  define example::server::vhost (
    $path = '/var/data',
  ) {
    include example::params

    $config = “/etc/example.d/${title}.conf”
    $service = $example::params::service

    file { $config :
      ensure  => present,
      owner   => 'example',
      group   => 'example',
      mode    => '0644',
      content => template('example/vhost.conf.erb'),
    }

    File[$config] ~> Service[$service]
  }

This defined type only creates a file resource with its name populated
by the title used when it gets defined and sets notification relationship
with service to make it restart when vhost file is changed.

This defined type can be used by other classes like a simple resource type to 
create as many vhost files as we need.::

  example::server::vhost { 'mydata' :
    path => '/path/to/my/data',
  }

Defined types can form relationships in a same way as resources do but you 
need to capitalize all elements of path to make reference.::

  File['/path/to/my/data'] -> Example::Server::Vhost['mydata']

Now we can work with text files using templates but what if we need to manage 
binary data files? Binary files or text files that will always be same can be 
placed into **files** directory of our module and then be taken by file 
resource.

Let's imagine that our client package need some binary data file we need to 
redistribute with it. Let's add file resource to our *example::client* class.::

  file { 'example_data' :
    path   => '/var/lib/example.data',
    owner  => 'example',
    group  => 'example',
    mode   => '0644',
    source => 'puppet:///modules/example/client.data',
  }

We have specified source as a special puppet URL scheme with module's and 
file's name. This file will be placed to specified location during puppet run. 
But on each run Puppet will check this files checksum overwriting it if it 
changes so don't use this method with mutable data. Puppet's fileserving works 
both in client-server and masterless modes.

Ok, we have all classes and resources we need to manage our hypothetical 
example service. Let's try to put everything together. Our example class 
defined inside *init.pp* is still empty so we can use it to declare all other 
classes.::

  class example {
    include example::params
    include example::client

    class { 'example::server::service' :
      port => '100',
    }

    example::server::vhost { 'site1' :
      path => '/data/site1',
    }

    example::server::vhost { 'site2' :
      path => '/data/site2',
    }

    example::server::vhost { 'test' :
      path => '/data/test',
    }

  }

Now we have entire module packed inside *example* class and we can just 
include this class to any node where we want to see our service running. 
Declaration of parametrized class also did override default port number from 
params file and we have three separate virtual hosts for out service. Client 
package is also included into this class.
