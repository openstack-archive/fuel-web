Resource duplication and file conflicts
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you have been developing your module that somehow uses services which are 
already in use by other components of OpenStack, most likely you will try to 
declare some of the same resources that have already been declared.
Puppet architecture doesn't allow declaration of resources that have same
type and title even if they do have same attributes.

For example, your module could be using Apache and has Service['apache'] 
declared. When you are running your module outside Fuel nothing else tries to 
control this service to and everything work fine. But when you will try to add 
this module to Fuel you will get resource duplication error because Apache is 
already managed by Horizon module.

There is pretty much nothing you can do about this problem because uniqueness 
of Puppet resources is one on its core principles. But you can try to solve 
the problem by one of following ways.

The best thing you can do is to try to use an already declared resource by 
settings dependencies to the other class that does use it. This will not work 
in many cases and you may have to modify both modules or move conflicting 
resource elsewhere to avoid conflicts.

Puppet does provide a good solution to this problem - **virtual resources**. 
The idea behind it is that you move resource declaration to separate class and 
make them virtual. Virtual resources will not be evaluated until you realize 
them and you can do it in all modules that do require this resources. 
The trouble starts when these resources have different attributes and complex 
dependencies. Most current Puppet modules doesn't use virtual resources and 
will require major refactoring to add them.

Puppet style guidelines advise to move all classes related with the same
service inside a single module instead of using many modules to work with
same service to minimize conflicts, but in many cases this approach
doesn't work.

There are also some hacks such are defining resource inside *if ! 
defined(Service['apache']) { ... }* block or using **ensure_resource** 
function from Puppet's stdlib.

Similar problems often arise then working with configuration files.
Even using templates doesn't allow several modules to directly edit same
file. There are a number of solutions to this starting from using
configurations directories and snippets if service supports them to
representing lines or configuration options as resources and managing
them instead of entire files.

Many services does support configuration directories where you can place
configuration files snippets. Daemon will read them all, concatenate and
use like it was a single file. Such services are the most convenient to
manage with Puppet. You can just separate you configuration and manage
its pieces as templates. If your service doesn't know how to work with
snippets you still can use them. You only need to create parts of your
configuration file in some directory and then just combine them all
using simple exec with *cat* command. There is also a special *concat*
resource type to make this approach easier. 

Some configuration files could have standard structure and can be managed
by custom resource types. For example, there is the *ini_file* resource
type to manage values in compatible configuration as single resources.
There is also *augeas* resource type that can manage many popular
configuration file formats.

Each approach has its own limitations and editing single file from
many modules is still non-trivial task in most cases.

Both resource duplication and file editing problems doesn't have a good
solution for every possible case and significantly limit possibility
of code reuse.

The last approach to solving this problem you can try is to modify files
by scripts and sed patches ran by exec resources. This can have unexpected
results because you can't be sure of what other operations are performed
on this configuration file, what text patterns exist there, and if your
script breaks another exec.

Puppet module containment
~~~~~~~~~~~~~~~~~~~~~~~~~

Fuel Library consists of many modules with a complex structure and
several dependencies defined between the provided modules.
There is a known Puppet problem related to dependencies between
resources contained inside classes declared from other classes.
If you declare resources inside a class or definition they will be
contained inside it and entire container will not be finished until all
of its contents have been evaluated.

For example, we have two classes with one notify resource each.::

  class a {
    notify { 'a' :}
  }

  class b {
    notify { 'b' :}
  }

  Class['a'] -> Class['b']

  include a
  include b

Dependencies between classes will force contained resources to be executed in 
declared order.
But if we add another layer of containers dependencies between them will not 
affect resources declared in first two classes.::

  class a {
    notify { 'a' :}
  }

  class b {
    notify { 'b' :}
  }

  class l1 {
    include a
  }

  class l2 {
    include b
  }

  Class['l1'] -> Class['l2']

  include 'l1'
  include 'l2'

This problem can lead to unexpected and in most cases unwanted behaviour
when some resources 'fall out' from their classes and can break the logic
of the deployment process.

The most common solution to this issue is **Anchor Pattern**. Anchors are 
special 'do-nothing' resources found in Puppetlab's stdlib module.
Anchors can be declared inside top level class and be contained
inside as any normal resource. If two anchors was declared they can be
named as *start* and *end* anchor. All classes, that should be contained
inside the top-level class can have dependencies with both anchors.
If a class should go after the start anchor and before the end anchor
it will be locked between them and will be correctly contained inside
the parent class.::

  class a {
    notify { 'a' :}
  }

  class b {
    notify { 'b' :}
  }

  class l1 {
    anchor { 'l1-start' :}
    include a
    anchor { 'l1-end' :}

    Anchor['l1-start'] -> Class['a'] -> Anchor['l1-end']
  }

  class l2 {
    anchor { 'l2-start' :}
    include b
    anchor { 'l2-end' :}

    Anchor['l2-start'] -> Class['b'] -> Anchor['l2-end']
  }

  Class['l1'] -> Class['l2']

  include 'l1'
  include 'l2'

This hack does help to prevent resources from randomly floating out of their 
places, but look very ugly and is hard to understand. We have to use this 
technique in many of Fuel modules which are rather complex and require such 
containment.
If your module is going to work with dependency scheme like this, you could 
find anchors useful too.

There is also another solution found in the most recent versions of Puppet. 
*Contain* function can force declared class to be locked within its 
container.::

  class l1 {
    contain 'a'
  }

  class l2 {
    contain 'b'
  }

Puppet scope and variables
~~~~~~~~~~~~~~~~~~~~~~~~~~

The way Puppet looks for values of variables from inside classes can be 
confusing too. There are several levels of scope in Puppet.
**Top scope** contains all facts and built-in variables and goes from the 
start of *site.pp* file before any class or node declaration. There is also a 
**node scope**. It can be different for every node block. Each class and 
definition start their own **local scopes** and their variables and resource 
defaults are available their. **They can also have parent scopes**.

Reference to a variable can consist of two parts 
**$(class_name)::(variable_name)** for example *$apache::docroot*. Class name 
can also be empty and such record will explicitly reference top level scope 
for example *$::ipaddress*.

If you are going to use value of a fact or top-scope variable it's usually a 
good idea to add two colons to the start of its name to ensure that you 
will get the value you are looking for.

If you want to reference variable found in another class and use fully 
qualified name like this *$apache::docroot*. But you should remember that 
referenced class should be already declared. Just having it inside your 
modules folder is not enough for it. Using *include apache* before referencing 
*$apache::docroot* will help. This technique is commonly used to make 
**params** classes inside every module and are included to every other class 
that use their values.

And finally if you reference a local variable you can write just *$myvar*. 
Puppet will first look inside local scope of current class of defined type, 
then inside parent scope, then node scope and finally top scope. If variable 
is found on any of this scopes you get the first match value.

Definition of what the parent scope is varies between Puppet 2.* and Puppet 
3.*. Puppet 2.* thinks about parent scope as a class from where current class 
was declared and all of its parents too. If current class was inherited 
from another class base class also is parent scope allowing to do popular 
*Smart Defaults* trick.::

  class a {
    $var = ‘a’
  }

  class b(
    $a = $a::var,
  ) inherits a {

  }

Puppet 3.* thinks about parent scope only as a class from which current class 
was inherited if any and doesn't take declaration into account.

For example::

  $msg = 'top'

  class a {
    $msg = "a"
  }

  class a_child inherits a {
    notify { $msg :}
  }

Will say 'a' in puppet 2.* and 3.* both. But.::

  $msg = 'top'

  class n1 {
    $msg = 'n1'
    include 'n2'
  }

  class n2 {
    notify { $msg :}
  }

  include 'n1'

Will say 'n1' in puppet 2.6, will say 'n1' and issue *deprecation warning* in 
2.7, and will say 'top' in puppet 3.*

Finding such variable references replacing them with fully qualified names is 
very important part Fuel of migration to Puppet 3.*

Where to find more information
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The best place to start learning Puppet is Puppetlabs' official learning 
course (http://docs.puppetlabs.com/learning/). There is also a special virtual 
machine image you can use to safely play with Puppet manifests.

Then you can continue to read Puppet reference and other pages of Puppetlabs 
documentation.

You can also find a number of printed book about Puppet and how to use it to 
manage your IT infrastructure.

Pro Puppet
http://www.apress.com/9781430230571

Pro Puppet. 2nd Edition
http://www.apress.com/9781430260400

Puppet 2.7 Cookbook
http://www.packtpub.com/puppet-2-7-for-reliable-secure-systems-cloud-computing-
cookbook/book

Puppet 3 Cookbook
http://www.packtpub.com/puppet-3-cookbook/book

Puppet 3: Beginners Guide
http://www.packtpub.com/puppet-3-beginners-guide/book

Instant Puppet 3 Starter
http://www.packtpub.com/puppet-3-starter/book

Pulling Strings with Puppet Configuration Management Made Easy
http://www.apress.com/9781590599785

Puppet Types and Providers Extending Puppet with Ruby
http://shop.oreilly.com/product/0636920026860.do

Managing Infrastructure with Puppet. Configuration Management at Scale
http://shop.oreilly.com/product/0636920020875.do
