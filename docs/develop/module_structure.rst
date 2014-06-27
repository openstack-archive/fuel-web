Contributing to Fuel Library
============================

This chapter explains how to add a new module or project into the Fuel Library,
how to integrate with other components,
and how to avoid different problems and potential mistakes.
The Fuel Library is a very big project
and even experienced Puppet users may have problems
understanding its structure and internal workings.

Adding new modules to fuel-library
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

*Case A. Pulling in an existing module*

If you are adding a module that is the work of another project
and is already tracked in a separate repo:

1. Create a review request with an unmodified copy
   of the upstream module from which you are working
   and *no* other related modifications.

   * This review should also contain the commit hash from the upstream repo
     in the commit message.
   * The review should be evaluated to determine its suitability
     and either rejected
     (for licensing, code quality, outdated version requested)
     or accepted without requiring modifications.
   * The review should not include code that calls this new module.

2.  Any changes necessary to make it work with Fuel
    should then be proposed as a dependent change(s).

*Case B. Adding a new module*

If you are adding a new module that is a work purely for Fuel
and is not tracked in a separate repo,
submit incremental reviews that consist of
working implementations of features for your module.

If you have features that are necessary but do not yet work fully,
then prevent them from running during the deployment.
Once your feature is complete,
submit a review to activate the module during deployment.

The Puppet modules structure
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Code that is contributed into the Fuel Library
should be organized into a Puppet module.
A module is a self-contained set of Puppet code
that is usually made to perform a specific function.
For example, you could have a module for each service
you are going to configure or for every part of your project.
Usually it is a good idea to make a module independent
but sometimes it may require or be required by other modules.
You can think of a module as a sort of library.

The most important part of every Puppet module is its **manifests** folder.
This folder contains Puppet classes and definitions
which also contain resources managed by this module.
Modules and classes also form namespaces.
Each class or definition should be placed into a single file
inside the manifests folder
and this file should have the same name as the class or definition.
The module should have a top level class
that serves as the module's entry point
and is named same as the module.
This class should be placed into the *init.pp* file.
This example module shows the standard structure
that every Puppet module should follow::

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

The first file in the *manifests* folder is named *init.pp*
and should contain the entry point class of this module.
This class should have the same name as the module::

  class example {

  }

The second file is *params.pp*.
This file is not mandatory but is often used
to store different configuration values and parameters
that are used by other classes of the module.
For example, it could contain the service name and package name
of our hypothetical example module.
Conditional statements might be included
if you need to change default values in different environments.
The *params* class should be named as a child
to the module's namespace as are all other classes of the module::

  class example::params {
    $service = 'example'
    $server_package = 'example-server'
    $client_package = 'example-client'
    $server_port = '80'
  }

All other files inside the manifests folder
contain classes as well and can perform any action
you might want to identify as a separate piece of code.
This generally falls into sub-classes that do not require its users
to configure the parameters explicitly,
or may be optional classes that are not required in all cases.
In the following example,
we create a client class that defines a client package
that will be installed and placed into a file called *client.pp*::

  class example::client {
    include example::params

    package { $example::params::client_package :
      ensure => installed,
    }

  }

As you can see, we have used the package name from params class.
Consolidating all values that might require editing into a single class,
as opposed to hardcoding them,
allows you to reduce the effort required
to maintain and develop the module further in the future.
If you are going to use any values from the params class,
you should include it first to force its code
to execute and create all required variables.

You can add more levels into the namespace structure if you want.
Let's create server folder inside our manifests folder
and add the *service.pp* file there.
It would be responsible for installing and running
the server part of our imaginary software.
Placing the class inside the subfolder adds one level
into the name of the contained class.::

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

Class *example::server::service* is **parametrized**
and can accept one parameter:
the port to which the server process should bind.
It also uses a popular "smart defaults" hack.
This class inherits the params class and uses its default values
only if no port parameter is provided.
In this case, you cannot use *include params*
to load the default values
because it is called by the *inherits example::params* clause
of the class definition.

Inside our class, we take several variables from the params class
and declare them as variables of the local scope.
This is a convenient practice to make their names shorter.

Next we declare our resources.
These resources are package, service, config file and config dir.
The package resource installs the package
whose name is taken from the variable
if it is not already installed.
File resources create the config file and config dir;
the service resource starts the daemon process and enables its autostart.

The final part of this class is the *dependency* declaration.
We have used a "chain" syntax to specify the order of evaluation
of these resources.
It is important to install the package first,
then install the configuration files
and only then start the service.
Trying to start the service before installing the package will definitely fail.
So we need to tell Puppet that there are dependencies between our resources.

The arrow operator that has a tilde instead of a minus sign (~>)
means not only dependency relationship
but also *notifies* the object to the right of the arrow to refresh itself.
In our case, any changes in the configuration file
would make the service restart and load a new configuration file.
Service resources react to the notification event
by restating the managed service.
Other resources may instead perform other supported actions.

The configuration file content is generated by the template function.
Templates are text files that use Ruby's erb language tags
and are used to generate a text file using pre-defined text
and some variables from the manifest.

These template files are located inside the **templates** folder
of the module and usually have the *erb* extension.
When a template function is called
with the template name and module name prefix,
Fuel tries to load this template and compile it
using variables from the local scope of the class function
from which the template was called.
For example, the following template saved in
the templates folder as *server.conf.erb file*
is a setting to bind the port of our service::

  bind_port = <%= @port %>

The template function will replace the 'port' tag
with the value of the port variable from our class
during Puppet's catalog compilation.

If the service needs several virtual hosts,
you need to define **definitions**,
which are similar to classes but, unlike classes,
they have titles like resources do
and can be used many times with different titles
to produce many instances of the managed resources.
Classes cannot be declared several times with different parameters.

Definitions are placed in single files inside the manifests directories
just as classes are
and are named in a similar way, using the namespace hierarchy.
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

This defined type only creates a file resource
with its name populated by the title
that is used when it gets defined.
It sets the notification relationship with the service
to make it restart when the vhost file is changed.

This defined type can be used by other classes
like a simple resource type to create as many vhost files as we need.::

  example::server::vhost { 'mydata' :
    path => '/path/to/my/data',
  }

Defined types can form relationships in the same way as resources do
but you need to capitalize all elements of the path to make the reference::

  File['/path/to/my/data'] -> Example::Server::Vhost['mydata']

This is works for text files but binary files must be handled differently.
Binary files or text files that will always be same
can be placed into the **files** directory of the module
and then be taken by the file resource.

To illustrate this, let's add a file resource for a file
that contains some binary data that must be distributed
in our client package.
The file resource is the *example::client* class::

  file { 'example_data' :
    path   => '/var/lib/example.data',
    owner  => 'example',
    group  => 'example',
    mode   => '0644',
    source => 'puppet:///modules/example/client.data',
  }

We have specified source as a special puppet URL scheme
with the module's and the file's name.
This file will be placed in the specified location when Puppet runs.
On each run, Puppet will check this file's checksum,
overwriting it if the checksum changes;
note that this method should not be used with mutable data.
Puppet's fileserving works in both client-server and masterless modes.

We now have all classes and resources that are required
to manage our hypothetical example service.
Our example class defined inside *init.pp* is still empty
so we can use it to declare all other classes
to put everything together::

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

Now we have the entire module packed inside the *example* class
and we can just include this class on any node
where we want to see our service running.
Declaration of the parametrized class
did override the default port number from the *params* file
and we have three separate virtual hosts for our service.
The client package is also included into this class.
