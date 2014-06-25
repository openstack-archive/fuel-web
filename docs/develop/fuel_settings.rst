Using Fuel settings
~~~~~~~~~~~~~~~~~~~

Fuel uses a special way to pass setting from Nailgun to Puppet manifests. 
Before the start of deployment process Astute uploads all settings, each 
server should have to the file */etc/astute.yaml* placed on every node.
When Puppet is run facter reads this file entirely into a single fact 
*$astute_settings_yaml*. Then these settings are parsed by parseyaml function 
at the very beginning of site.pp file and set as rich data structure called 
*$fuel_settings*. All of the setting used during node deployment are stored 
there and can be used anywhere in Puppet code.
For example, single top level variables are available as 
*$::fuel_settings['debug']*. More complex structures are also available as 
values of *$::fuel_settings* hash keys and can be accessed like usual hashes 
and arrays.
There are also a lot of aliases and generated values that help you get needed 
values easier. You can always create variables from any of settings hash keys 
and work with this variable within your local scope or from other classes 
using fully qualified paths.::

  $debug = $::fuel_settings['debug']

Some variables and structures are generated from settings hash by filtering 
and transformation functions. For example there is $node structure.::

  $node = filter_nodes($nodes_hash, 'name', $::hostname)

It contains only settings of current node filtered from all nodes hash.

If you are going to use your module inside Fuel Library and need some
settings you can just get them from this *$::fuel_settings* structure.
Most variables related to network and OpenStack 
services configuration are already available there and you can use them as 
they are. But if your modules requires some additional or custom settings 
you'll have to either use **Custom Attributes** by editing json files before 
deployment, or, if you are integrating your project with Fuel Library, you 
should contact Fuel UI developers and ask them to add your configuration 
options to Fuel setting panel.

Once you have finished definition of all classes you need inside your module 
you can add this module's declaration either into the Fuel manifests such as 
*cluster_simple.pp* and *cluster_ha.pp* located inside
*osnailyfacter/manifests* folder or to the other classes that are already 
being used if your additions are related to them.

Example module
~~~~~~~~~~~~~~

Let's demonstrate how to add new module to the Fuel Library by adding a simple 
class that will change terminal color of Red Hat based systems.
Our module will be named *profile* and have only one class.::

  profile
  profile/manifests
  profile/manifests/init.pp
  profile/files
  profile/files/colorcmd.sh

init.pp could have a class definition like this.::

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

This class just downloads *colorcmd.sh* file and places it to the defined 
location if this class is run on Red Hat or CentOS system. The profile module
can be added to Fuel modules by uploading its folder to */etc/puppet/modules*
on the Fuel Master node.

Now we need to declare this module somewhere inside Fuel manifests. Since this 
module should be run on every server, we can use our main *site.pp* manifest 
found inside the *osnailyfacter/examples* folder. On the deployed master node
this file will be copied to */etc/puppet/manifests* and used to deploy Fuel
on all other nodes.
The only thing we need to do here is to add *include profile* to the end of 
*/etc/puppet/manifests/site.pp* file on already deployed master node and to 
*osnailyfacter/examples/site.pp* file inside Fuel repository.

Declaring a class outside of node block will force this class to be included 
everywhere. If you want to include you module only on some nodes, you can add 
its declaration inside *cluster_simple* and *cluster_ha* classed to the blocks 
associated with required node's role.

You can add some additional logic to allow used to enable or disable this 
module from Fuel UI or at least by passing Custom Attributes to Fuel 
configuration.::

  if $::fuel_settings['enable_profile'] {
    include 'profile'
  }

This block uses the *enable_profile* variable to enable or disable inclusion of 
profile module. The variable should be passed from Nailgun and saved to 
*/etc/astute.yaml* files of managed nodes.
You can do it by either downloading settings files and manually editing
them before deployment or by asking Fuel UI developers to include additional
options to the settings panel.
