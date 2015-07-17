Package version problems
========================

The introduction of OpenStack updates brought up one non-obvious problem with
package versions. In order to update a package the new version should be
considered higher than the previous one. Package versions are compared between
the old and the new packages and a package manager then decides if the new
package installation is an upgrade or a downgrade. The algorithm used to
compare version numbers is different for rpm and deb packages and Puppet uses
its own implementation.

Previously we have never tried to update our OSCI packages from the previous
version and did not think about version number comparison and many packages
were named badly.

For example:
2014.1.fuel5.0-mira4 2014.1.1.fuel5.1-mira0
In this case most of version comparison algorithms would find 5.0 version
to be larger than 5.1.

::

    * Native Puppet
    2014.1.fuel5.0-mira4 > 2014.1.1.fuel5.1-mira0
    * Puppet RPMVERCMP
    2014.1.fuel5.0-mira4 < 2014.1.1.fuel5.1-mira0
    * Native RPM
    0:2014.1.fuel5.0-mira4 < 0:2014.1.1.fuel5.1-mira0
    * Native DEB
    2014.1.fuel5.0-mira4 > 2014.1.1.fuel5.1-mira0

This is because we have not been using correct separation between package
version and revision and these packages should have been named like this:

::

  2014.1-fuel5.0.mira4 2014.1.1-fuel5.1.mira0
  * Native Puppet
  2014.1-fuel5.0.mira4 < 2014.1.1-fuel5.1.mira0
  * Puppet RPMVERCMP
  2014.1-fuel5.0.mira4 < 2014.1.1-fuel5.1.mira0
  * Native RPM
  0:2014.1-fuel5.0.mira4 < 0:2014.1.1-fuel5.1.mira0
  * Native DEB
  2014.1-fuel5.0.mira4 < 2014.1.1-fuel5.1.mira0

This also affect other packages not only OpenStack ones.

::

  1.0.8.fuel5.0-mira0  1.0.8-fuel5.0.2.mira1
  * Native Puppet
  1.0.8.fuel5.0-mira0 > 1.0.8-fuel5.0.2.mira1
  * Puppet RPMVERCMP
  1.0.8.fuel5.0-mira0 < 1.0.8-fuel5.0.2.mira1
  * Native RPM
  0:1.0.8.fuel5.0-mira0 > 0:1.0.8-fuel5.0.2.mira1
  * Native DEB
  1.0.8.fuel5.0-mira0 > 1.0.8-fuel5.0.2.mira1

The most complex part of this problem is that even if we change our current
package naming to be correct one we cannot change packages already installed
and used in production. So we have raised epoch for many 5.0.2 packages to make
it possible to upgrade them from incorrectly named 5.0 packages and move to the
correct naming scheme. In Fuel 5.1 and higher we will be using only correct
naming and epoch can be removed.

::

  0:1.0.8.fuel5.0-mira0 1:1.0.8-fuel5.0.2.mira1
  * Native Puppet
  0:1.0.8.fuel5.0-mira0 < 1:1.0.8-fuel5.0.2.mira1
  * Puppet RPMVERCMP
  0:1.0.8.fuel5.0-mira0 < 1:1.0.8-fuel5.0.2.mira1
  * Native RPM
  0:1.0.8.fuel5.0-mira0 < 1:1.0.8-fuel5.0.2.mira1
  * Native DEB
  0:1.0.8.fuel5.0-mira0 < 1:1.0.8-fuel5.0.2.mira1

As you can see, raising epoch allows us to set which version is higher
regardless its actual value.
Removing epoch from 5.1 packages makes it impossible to seamlessly upgrade
5.0 or 5.0.2 packages to 5.1 ones. It’s not really a problem because we
don’t support such upgrades anyway but if you do try to make such upgrade
manually you should remove old packages manually before installing new packages.

* My version checkers for all algorithms: https://github.com/dmitryilyin/vercmp
* RPM naming guidelines: http://fedoraproject.org/wiki/Packaging:NamingGuidelines
* RPM comparison: http://fedoraproject.org/wiki/Archive:Tools/RPM/VersionComparison
* DEB naming guidelines and version comparison: https://www.debian.org/doc/debian-policy/ch-controlfields.html#s-f-Version
