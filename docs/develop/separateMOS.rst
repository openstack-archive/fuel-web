Separate Mirantis OpenStack and Linux Repositories
==================================================

Starting with Fuel 6.1, the repositories for
Mirantis OpenStack and Linux packages are separate.

Having separate repositories gives you the following
advantages:

* You can run base distributive updates and
  Mirantis OpenStack updates during the product life cycle.

* You can see what packages are provided by
  Mirantis OpenStack and what packages provided by the base distributive.

* You can download security updates
  independently for the base distributive and for Mirantis OpenStack.

* You can see sources of the base distributive and
  Mirantis OpenStack packages.

* You can see the debug symbols of the base distributive and
  Mirantis OpenStack packages.

* As a Fuel Developer, you can have the same approach for making
  changes to Fuel components and their dependencies.

Types of software packages
--------------------------

All software packages deployed starting with Fuel 6.1
are divided into the following categories:

#. *Upstream package*: A package from the supported release of the base distributive
   is reused from the distributive repositories directly, without modifications specific
   to Mirantis OpenStack.

#. *Mirantis OpenStack specific package*: A package specific to Mirantis OpenStack that does not
   exist in any release of the base distributive, or any of the base distributive's
   upstream distributions.

#. *Divergent package*: A package that is based on a version of the same
   package from any release of the base distributive or its upstream distributions,
   and includes a different software version than the corresponding *upstream
   package*, or additional modifications that are not present in the *upstream
   package*, or both.

   #. *Upgraded package*: A variant of *divergent package* that includes a
      newer software version than the corresponding *upstream package*.

   #. *Holdback package*: a variant of *divergent package* constituting a
      temporary replacement for an *upstream package* to fix a regression
      introduced in the supported release of the base distributive. It is published
      in a Mirantis OpenStack repository after a regression is detected, and is
      removed from that repository as soon as the regression is either resolved
      in the upstream package, or addressed elsewhere in Mirantis OpenStack.

.. note:: Downgraded packages with the upstream version lower than the version
          available in the base distributive are not allowed.

Different releases of Mirantis OpenStack can put the same software package in different
categories.

All kinds of divergence from the base distributive should be kept to a minimum. As
many of Mirantis OpenStack dependencies as possible should be satisfied by upstream packages
from the supported release of the base distro. When possible, Mirantis OpenStack patches and
Mirantis OpenStack specific packages should be contributed back to the base distributives.

Distributing Mirantis OpenStack packages
----------------------------------------

Released Mirantis OpenStack packages are be distributed as part of the Fuel ISO image. Upstream
packages and any other IP protected by respective operating system vendors are not
included in Fuel ISO images. Regular updates to the Mirantis OpenStack
distribution are delivered through online Mirantis OpenStack mirrors.

Mirantis OpenStack mirrors structure
------------------------------------

Mirantis OpenStack mirrors are organized in the same way as base distro mirrors.

Every supported operating system has its own set of repositories containing Mirantis OpenStack packages
per release (mos6.1, mos7.0 etc). These repositories contain only packages
with Mirantis OpenStack specific modifications, and no upstream packages from the
corresponding base distro.

As a user you can create and maintain local copies of the base distro and Mirantis OpenStack mirrors.
This allows you to use the repositories in completely isolated environments or
create your own mirrors to pass the extended validation before a package update
roll-out across your production environment.

Top level Mirantis OpenStack mirror structure
---------------------------------------------

::

  /
  +--+centos
  |  |
  |  +--+6
  |  |  |
  |  |  +--+mos6.0
  |  |  |
  |  |  +--+mos6.1
  |  |
  |  +--+7
  |     |
  |     +--+mos7.0
  |     |
  |     +--+mos7.1
  |
  +--+ubuntu
     |
     +--+dists
     |
     +--+pool
     |
     +--+...

Debian based mirror structure
-----------------------------

Mirantis OpenStack mirrors include several repositories (updates, security, proposed)
built in the same way as the base operating system mirror (Debian or Ubuntu). Repository sections
are organized in the same way (main, restricted) in accordance with the package licenses
(non-free).

::

  $(OS_MIRROR)                 $(MOS_MIRROR)
  +                            +
  |                            |
  +--+ubuntu                   +--+ubuntu
     |                            |
     +--+dists                    +--+dists
     |  |                         |  |
     |  +--+precise-backport      |  +--+mos6.1-proposed
     |  |                         |  |
     |  +--+precise-proposed      |  +--+mos6.1-security
     |  |                         |  |
     |  +--+precise-security      |  +--+mos6.1-updates
     |  |                         |  |
     |  +--+precise-updates       |  +--+mos6.1
     |  |                         |  |
     |  +--+precise               |  +--+mos7.0-proposed
     |  |                         |  |
     |  +--+trusty-backport       |  +--+mos7.0-security
     |  |                         |  |
     |  +--+trusty-proposed       |  +--+mos7.0-updates
     |  |                         |  |
     |  +--+trusty-security       |  +--+mos7.0
     |  |                         |
     |  +--+trusty-updates        +--+indices
     |  |                         |  |
     |  +--+trusty                |  +--+...
     |                            |
     +--+indices                  +--+pool
     |  |                         |  |
     |  +--+...                   |  +--+main
     |                            |  |  |
     +--+pool                     |  |  +--+a
     |  |                         |  |  |
     |  +--+main                  |  |  +--+...
     |  |                         |  |  |
     |  +--+multiverse            |  |  +--+z
     |  |                         |  |
     |  |--+restricted            |  |--+restricted
     |  |                         |     |
     +  |--+universe              |     +--+a
     |                            |     |
     |--+...                      |     +--+...
                                  |     |
                                  |     +--+z
                                  |
                                  +--+project
                                     |
                                     +--+mos-archive-keyring.gpg
                                     |
                                     +--+mos-archive-keyring.sig

Red Hat based mirror structure
------------------------------

Mirantis OpenStack mirrors include several repositories (operating system, updates, Fasttrack) built
in the same way as base distro mirror (Red Hat or CentOS).

::

  $(OS_MIRROR)                           $(MOS_MIRROR)
  +                                      +
  |                                      |
  +--+centos-6                           +--+centos-6
  |  |                                   |  |
  |  +--+...                             |  +--+mos6.1
  |                                      |  |
  +--+centos-7                           |  +--+mos7.0
     |                                   |     |
     +--+7                               |     +--+os
        |                                |     |  |
        +--+os                           |     |  +--+x86_64
        |  |                             |     |     |
        |  +--+x86_64                    |     |     +--+Packages
        |     |                          |     |     |  |
        |     +--+Packages               |     |     |  +--+*.rpm
        |     |  |                       |     |     |
        |     |  +--+*.rpm               |     |     +--+RPM-GPG-KEY-MOS7.0
        |     |                          |     |     |
        |     +--+RPM-GPG-KEY-CentOS-7   |     |     +--+repodata
        |     |                          |     |        |
        |     +--+repodata               |     |        +--+*.xml,*.gz
        |        |                       |     |
        |        +--+*.xml,*.gz          |     +--+updates
        |                                |        |
        +--+updates                      |        +--+x86_64
           |                             |           |
           +--+x86_64                    |           +--+Packages
              |                          |           |  |
              +--+Packages               |           |  +--+*.rpm
              |  |                       |           |
              |  +--+*.rpm               |           +--+repodata
              |                          |              |
              +--+repodata               |              +--+*.xml,*.gz
                 |                       |
                 +--+*.xml,*.gz          +--+centos-7
                                            |
                                            +--+mos7.1
                                            |
                                            +--+mos8.0

Repositories priorities
-----------------------

Handling multiple package repositories in Nailgun is expanded to
allow the user to set priorities during deployment.

Default repository priorities are arranged so that packages from Mirantis OpenStack
repositories are preferred over packages from the base distro. On Debian based
systems, the force-downgrade APT pinning priorities are used for Mirantis OpenStack
repositories to make sure that, when a package is available in a Mirantis OpenStack
repository, it is always preferred over the package from the base distro, even if
the version in the Mirantis OpenStack repository is lower.

Fuel developer repositories
---------------------------

The build system allows developers to build custom packages. These packages
are placed into a special repository which can be specified in Nailgun
to deliver these packages to an environment. APT pinning priority for these
repositories is higher than the base distro and Mirantis OpenStack repositories.
Accordingly, Yum repository priority value is lower than the base distro and
Mirantis OpenStack repositories.

Holdback repository
-------------------

The purpose of the holdback repository is to ensure the highest quality of the Mirantis OpenStack
product. If there is an *upstream* package that breaks the product, and this
cannot be fixed in a timely manner, the Mirantis OpenStack team publishes the package
proven stable to the "mosXX-holdback" repository. This repository is
automatically configured on all installations with the priority higher than the base
distro repositories.

The case when the base distro vendor releases a fixed version of a problem package
is covered by Mirantis OpenStack system tests.

Package versioning requirements
-------------------------------

A package version string for a *Mirantis OpenStack specific* or a *divergent* package must not
include registered trademarks of base distro vendors, and should include the "mos"
keyword.

Every new revision of a *Mirantis OpenStack specific* or a *divergent* package targeted to a Mirantis OpenStack
release (including the corresponding update repository) must have a package version
greater than or equal to the versions of the same package in all previous
releases of Mirantis OpenStack (base, update, security repositories), as well as versions of
the same package previously published in any repos for this Mirantis OpenStack release.

For example, there must be no package version downgrades in the following Mirantis OpenStack
release progression (where 6.1.1 matches the state of update repository at the
time of 6.1.1 maintenance release):

    6.0 <= 6.0.1 <= 6.1 <= 6.1.1 <= 6.1.2 <= 7.0

Package version of a *divergent* package (including *upgraded* and *holdback*
packages) must be constructed in a way that allows the *upstream* package
with the same software version to be automatically considered for an upgrade by
the package management system as soon as the divergent package is removed from the
Mirantis OpenStack repositories. This simplifies the phasing out of divergent packages in favor of the
upstream packages between major Mirantis OpenStack releases, but due to the repository priorities
defined above, does not lead to new upstream packages superceding the *upgraded*
packages available from Mirantis OpenStack repositories when applying updates.

Every new revision of a *divergent* package must have a package version greater
than previous revisions of the same package that is published to the same
repository for that Mirantis OpenStack release. Its version should be lower than the version of
the corresponding *upstream* package.

When the same package version is ported from one Mirantis OpenStack release to another without
modifications (i.e. same upstream version and same set of patches), a new package
version should include the full package version from the original Mirantis OpenStack release.

Debian package versioning
-------------------------

Versioning requirements defined in this section apply to all software packages
in all Mirantis OpenStack repositories for Debian based distros. The standard terms defined in
Debian Policy are used to describe package version components: epoch,
upstream version, Debian revision.

Upstream version of a package should exactly match the software version,
without suffixes. Introducing epoch or increasing epoch relative to a base distro
should be avoided.

Debian revision of a Mirantis OpenStack package should use the following format::

    <revision>~<base-distro-release>+mos<subrevision>

In Mirantis OpenStack specific packages, revision must always be "0"::

    fuel-nailgun_6.1-0~u14.04+mos1

In *divergent* packages, revision should include as much of the Debian revision
of the corresponding *upstream* package as possible while excluding the base
distro vendor's trademarks, and including the target distribution version::

    qemu_2.1.0-1           -> qemu_2.1.0-1~u14.04+mos1
    ohai_6.14.0-2.3ubuntu4 -> ohai_6.14.0-2.3~u14.04+mos1

Subrevision numbering starts from 1. Subsequent revisions of a package using
the same upstream version and based on the upstream package with the same
Debian revision should increment the subrevision::

    ohai_6.14.0-2.3~u14.04+mos2
    ohai_6.14.0-2.3~u14.04+mos3

Subsequent revision of a package that introduces a new upstream version or new
base distro package revision should reset the subrevision back to 1::

    ohai_6.14.0-3ubuntu1 -> ohai_6.14.0-3~u14.04+mos1

Versioning of packages in post-release updates
++++++++++++++++++++++++++++++++++++++++++++++

Once a Mirantis OpenStack release reaches GA, the primary package repository for the release
is frozen, and subsequent updates are published to the updates repositories.

Most of the time, only a small subset of modifications (including patches,
metadata changes, etc.) is backported to updates for old Mirantis OpenStack releases.
When an updated package includes only a subset of modifications, its version
should include the whole package version from the primary repository, followed
by a reference to the targeted Mirantis OpenStacj release, and an update subrevision, both
separated by "+"::

    mos6.1:         qemu_2.1.0-1~u14.04+mos1
    mos7.0:         qemu_2.1.0-1~u14.04+mos1
    mos7.1:         qemu_2.1.0-1~u14.04+mos2
    mos6.1-updates: qemu_2.1.0-1~u14.04+mos1+mos6.1+1
    mos7.0-updates: qemu_2.1.0-1~u14.04+mos1+mos7.0+1

If the whole package along with all the included modifications is backported from
the current release to updates for an old Mirantis OpenStack release, its version should include
the whole package version from the current release, followed by a reference to
the targeted Mirantis OpenStack release separated by "~", and an update subrevision, separated
by "+"::

    mos6.1:         qemu_2.1.0-1~u14.04+mos1
    mos7.0:         qemu_2.1.0-1~u14.04+mos1
    mos7.1:         qemu_2.1.0-1~u14.04+mos2
    mos6.1-updates: qemu_2.1.0-1~u14.04+mos2~mos6.1+1
    mos7.0-updates: qemu_2.1.0-1~u14.04+mos2~mos7.0+1

The same rule applies if modifications include an upgrade to a newer software
version::

    mos6.1:         qemu_2.1.0-1~u14.04+mos1
    mos7.0:         qemu_2.1.0-1~u14.04+mos1
    mos7.1:         qemu_2.2+dfsg-5exp~u14.04+mos3
    mos6.1-updates: qemu_2.2+dfsg-5exp~u14.04+mos3~mos6.1+1
    mos7.0-updates: qemu_2.2+dfsg-5exp~u14.04+mos3~mos7.0+1

Debian package metadata
-----------------------

All *Mirantis OpenStack specific* and *divergent* packages must have the following metadata:

#. The latest entry in the debian/changelog must contain:

   - reference to the targeted Mirantis OpenStack release series (e.g. mos6.1)

   - reference to the organization that produced the package (Mirantis)

   - commits (full git commit sha1) in all source code repositories that the
     package was built from: build repository commit if both source code and
     build scripts are tracked in the same repository (git-buildpackage style),
     or both source and build repository commits if the source code is tracked in a
     separate repository from build scripts

#. Maintainer in debian/control must be Mirantis OpenStack Team

Example of a valid debian/changelog entry::

  keystone (2014.2.3-1~u14.04+mos1) mos6.1; urgency=low

   * Source commit: 17f8fb6d8d3b9d48f5a4206079c18e84b73bf36b
   * Build commit: 8bf699819c9d30e2d34e14e76917f94daea4c67f

  -- Mirantis OpenStack Team <mos@mirantis.com> Sat, 21 Mar 2015 15:08:01 -0700

If the package is a backport from a different release of a base distro (e.g. a
backport of a newer software version from Ubuntu 14.10 to Ubuntu 14.04), the
exact package version which the backport was based on must also be specified in
the debian/changelog entry, along with the URL where the source package for
that package version can be obtained from.

The following types of URLs may be used, in the order of preference:

#. git-buildpackage or similar source code repository,

#. deb package pool directory,

#. direct dpkg source (orig and debian) download links.

Package life cycle management
-----------------------------

To deliver  the high quality of the product, Mirantis OpenStack teams produce package updates
during the product life cycle when required.

Packaging life cycle follows the Mirantis OpenStack product lifecycle (Feature Freeze,
Soft Code Freeze, Hard Code Freeze, Release, Updates).

The Mirantis OpenStack mirror is modified on the Hard Code Freeze announcement. A new Mirantis OpenStack
version is created to allow the developers continue on a new release.

After a GA release, all packages are placed in the updates or security
repository

::

  V^                                                    +---------------------+
   |                                                    |7.1-updates
   |                                                    |
   |                                                    |
   |                                      +-----------------------------------+
   |                                      |8.0-dev      |
   |                                      |             |
   |                                      |             |
   |                        +-------------------------------------------------+
   |                        |6.1-updates  |             |
   |                        |             |             |
   |                        |             |             |
   |            +-------------------------+-------------+---------------------+
   |            |7.1-dev    |            7.1-HCF       7.1 GA
   |            |           |
   |            |           |
   +------------+-----------+------------------------------------------------->
   6.1 dev    6.1 HCF     6.1 GA                                             t


Patches for the security vulnerabilities are placed in the *security* repository.
They are designed to change the behavior of the package as little as possible.

Continous integration testing against base distro updates
---------------------------------------------------------

As part of the product lifecycle, there are system tests that
verify functionality of Mirantis OpenStack against:

- the current state of the base distro mirror (base system plus released updates),
  to check stability of the current release
- the current state of the Stable Release Updates or Fasttrack repository,
  to check if package candidates introduce any regressions

Handling of system test results
-------------------------------

If the system test against proposed or Fasttrack repositories reveals
one or several packages that break the Mirantis OpenStack functionality, the Mirantis OpenStack teams provide
one of the following solutions:

- solve the issue on the product side by releasing fixed Mirantis OpenStack packages through
  the "updates" repository
- raise a debate with base distro SRU reviewing team regarding problem packages
- (if none of the above helps) put working version of a problem package to
  the holdback repository

Also, any package that failed the system test, is reflected on the
release status page.

Release status page
-------------------

To ensure that the Mirantis OpenStack customers have full information on the release stability, all
packages that produce system test failures must are also reported in several
different ways:

- Web: Via the `status page <https://fuel-infra.org/>`_.
- on deployed nodes: Via a hook that updates MOTD using the `Fuel Infra website <https://fuel-infra.org/>`_.
- on deployed nodes: Via an APT pre-hook that checks the status via the above
  website, and gives a warning if an ``apt-get update`` command is issued

Packages building module
------------------------

Fuel DEB packages build routinely are disabled by default, and kept for the
Fuel CI purposes only (nightly and test product builds). The release product
ISO contains Fuel DEB packages from the Mirantis OpenStack repository. Updates to the Fuel
DEB packages are consumed from the Mirantis OpenStack mirror directly on the Fuel Master
node.

The explicit list of Fuel DEB packages is the following:

* fencing-agent
* nailgun-mcagents
* nailgun-net-check
* nailgun-agent
* python-tasklib

Docker containers building module
---------------------------------

All Dockerfile configs are adjusted to include both upstream and Mirantis OpenStack
repositories.

ISO assembly module
-------------------

ISO assembly module excludes all the parts mentioned above.

Offline installations
---------------------

To support offline installation cases there is a Linux console
script that mirrors the public base distro and Mirantis OpenStack mirrors to a given location,
allowing to put these local sources as input for the appropriate menu entry of the
Fuel "Settings" tab on UI, or specify directly via Fuel CLI. In case of
deb-based base distro, Mirantis OpenStack requires packages from multiple sections of a given
distribution (main, universe, multiverse, restricted), so the helper script
will mirror all packages from the components specified above. Requirements:

* input base distro mirror URL
* input MOS mirror URL
* ability to run as cronjob to update base distro and Mirantis OpenStack mirrors
