Using Fuel settings
~~~~~~~~~~~~~~~~~~~

Fuel uses a special method to pass settings from Nailgun to Puppet manifests:

- Before the deployment process begins,
  Astute uploads all settings
  to the the */etc/astute.yaml* files that are located on each node.
- When Puppet is run,
  Facter reads the contents of all these  */etc/astute.yaml* files
  and creates a single file called *$astute_settings_yaml*.
- The **parseyaml** function (at the beginning of the *site.pp* file)
  then parses these settings
  and creates a rich data structure called *$fuel_settings*.
  All of the settings used during node deployment are stored there
  and can be used anywhere in Puppet code.

For example, single top level variables are available as
*$::fuel_settings['debug']*.
More complex structures are also available as
values of *$::fuel_settings* hash keys
and can be accessed like normal hashes and arrays.
Many aliases and generated values are provided
to help you retrieve values easily.
You can create a variable from any hash key in *$fuel_settings*
and work with this variable within your local scope
or from other classes, using fully qualified paths::

  $debug = $::fuel_settings['debug']

Some variables and structures are generated from the settings hash
by filtering and transformation functions.
For example the $node structure only contains
settings of the current node,
filtered from the has of all nodes.
It can be accessed as::

  $node = filter_nodes($nodes_hash, 'name', $::hostname)

If you are going to use your module inside the Fuel Library
and need some settings,
you can get them from this *$::fuel_settings* structure.
Most variables related to network and OpenStack services configuration
are already available there and you can use them as they are.
If your modules require some additional or custom settings,
you must either use **Custom Attributes**
by editing the JSON files before deployment, or,
if you are integrating your project with the Fuel Library,
you can contact the Fuel UI developers
and ask them to add your configuration options to the Fuel setting panel.

After you have defined all classes you need inside your module,
you can add this module's declaration
into the Fuel manifests such as
*cluster_simple.pp* and *cluster_ha.pp* located inside
the *osnailyfacter/manifests* folder
or, if your additions are related to another class,
can add them into that class.

Example module
~~~~~~~~~~~~~~

To demonstrate how to add a new module to the Fuel Library,
let us add a simple class
that changes the terminal color of Red Hat based systems.
Our module is named *profile* and has only one class.::

  profile
  profile/manifests
  profile/manifests/init.pp
  profile/files
  profile/files/colorcmd.sh

init.pp could have a class definition such as:::

  class profile {
    if $::osfamily == 'RedHat' {
      file { 'colorcmd.sh' :
        ensure   => present,
        owner    => 'root',
        group    => 'root',
        mode     => '0644',
        path     => "/etc/profile.d/colorcmd.sh",
        source   => 'puppet:///modules/profile/colorcmd.sh',
      }
    }
  }

This class downloads the *colorcmd.sh* file
and places it in the defined location
when the class is run on a Red Hat or CentOS system.
The profile module can be added to Fuel modules
by uploading its folder to */etc/puppet/modules*
on the Fuel Master node.

Now we need to declare this module somewhere inside the Fuel manifests.
Since this module should be run on every server,
we can use our main *site.pp* manifest
found inside the *osnailyfacter/examples* folder.
On the deployed master node,
this file will be copied to */etc/puppet/manifests*
and used to deploy Fuel on all other nodes.
The only thing we need to do here is to add the *include profile*
to the end of the */etc/puppet/manifests/site.pp* file
on the already deployed master node
and to the *osnailyfacter/examples/site.pp* file inside the Fuel repository.

Declaring a class outside of a node block
forces this class to be included everywhere.
If you want to include your module only on some nodes,
you can add its declaration
to the blocks associated with the role that is running on those nodes
inside the *cluster_simple* and *cluster_ha* classes.

You can add some additional logic to allow this module to be disabled,
either from the Fuel UI or by passing Customer Attributes
to the Fuel configuration.::

  if $::fuel_settings['enable_profile'] {
    include 'profile'
  }

This block uses the *enable_profile* variable
to enable or disable inclusion of the profile module.
The variable should be passed from Nailgun and saved
to the */etc/astute.yaml* files on managed nodes.
You can do this either by downloading the settings files
and manually editing them before deployment
or by asking the Fuel UI developers to include additional options
in the settings panel.
