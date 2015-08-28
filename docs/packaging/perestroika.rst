Perestroika build system
========================

Introduction
------------

Fuel 7.0 introduces a new build system called Perestroika. It uses
standard upstream Linux distribution tools in order to:

* build packages (SBuild/Mock)
* publish packages to repositories
* manage package repositories (using reprepro/createrepo tools).

Every package is built in a clean and up-to-date buildroot. Packages,
their dependencies, and build dependencies are fully self-contained
for each Mirantis OpenStack release. Any package included in any
release can be rebuilt at any point in time using only the packages
from that release.

The package build CI is reproducible and can be recreated from scratch
in a repeatable way.

Perestroika is based on Docker which provides an easy distribution.
Each supported Linux distribution contains proper Docker images with
necessary tools and scripts.

For the advantages of Perestroika over OBS build system, see
`Replace OBS with another build system <http://specs.fuel-infra.org/fuel-specs-master/specs/7.0/replace-obs.html>`_.

Perestroika structure
---------------------

Code storage
~~~~~~~~~~~~

Gerrit code review system is used as a code storage.

Gerrit projects structure:

* Mirantis OpenStack/Fuel Master node packages:

  - code projects: *[customer-name]/openstack/{package name}*
  - spec projects: *[customer-name]/openstack-build/{package name}-build*

* Mirantis OpenStack Linux packages:

  - code/spec projects: *[customer-name]/packages/{distribution}/{packagename}*

* Fuel Master node Linux packages (separated from Mirantis OpenStack
  Linux in 7.0):

  - code/spec projects: *[customer-name]/packages/fuel/{distribution}/{package name}*

* Versioning scheme supported by project branches:

  - OpenStack: *openstack-ci/fuel-{fuel version}/{openstack version}*
  - Mirantis OpenStack Linux/Fuel Master node: *{fuel version}*

**where**
 *  *customer-name* should be empty for Mirantis OpenStack projects due
    to a backward compatibility with releases older than 7.0.
 *  supported values of the ``{distribution}`` parameter are {centos6},
    {centos7} and {trusty}. 

Scheduler
~~~~~~~~~

This part is based on Jenkins CI tool. All jobs are configured using
``jenkins-job-builder``. Jenkins has a separate set of jobs for each
*[customer name]+[fuel version]* case. Gerrit-trigger is configured
to track events from the *{version}* branch of all the *[customer-name]*
Gerrit projects.

Each set of jobs contains:

* jobs for OpenStack packages for a cluster (``.rpm`` and ``.deb``)
* jobs for Mirantis OpenStack Linux packages for a cluster (``.rpm``
  and ``.deb``)
* jobs for OpenStack packages for Fuel Master node (``.rpm``). In case
  of using cluster packages, they are optional.
* jobs for non-OpenStack Fuel Master node packages (``.rpm``)
* jobs for Fuel packages (``.rpm`` and ``.deb``)
* a job for package publishing

Build workers
~~~~~~~~~~~~~

These are hardware nodes with preconfigured build tools for all the
supported distributions. They are configured as Jenkins slaves.

Each worker contains:

* preconfigured Docker images with native build tools for each
  distribution type:

  - ``mockbuild`` builds packages using Mock (CentOS 6 and 7 target
    distributions are supported).
  - ``sbuild`` builds packages using SBuild tool (Ubuntu Trusty
    Tahr target distribution is supported only).

* prepared minimal build chroots for all the supported distributions:

  - These chroots are updated on a daily basis in order to be up-to-date
    against the upstream state.
  - Chroot updating is performed by a separate Jenkins job.
  - No build jobs can run on a build host while the updating Jenkins job
    is running on it.

**Building stage flow**:

#. Checking out sources from Gerrit.
#. Preparing sources to build (creating tarball files, updating
   changelogs).
#. Building sources (performed in an isolated environment inside a
   Docker container).
#. Getting the build stage exit status, build logs, and built
   packages.
#. Parsing and archiving build logs for Jenkins artifacts.

Packaging CI uses short-lived Docker containers to perform package
building. Docker images contain preconfigured build tools only. There
are no chroots inside images. Build chroots are mounted to a Docker
container at start in a read-only mode. Additionally *tmpfs* partition
is mounted over a read-only chroot folder with AUFS overlays inside
a Docker container. The container is destroyed once the build stage is
completed.

**Goals of this scheme**:

* It can run a number of containers with the only chroot simultaneously
  on the same build host.
* There is no need to perform clean-up operations after the build (all
  changes matter inside the container only and will be purged after the
  container is destroyed).
* *tmpfs* works much faster than disk FS/LVM snapshots.

Publisher node
~~~~~~~~~~~~~~

If the build stage finishes successfully, Jenkins runs a publishing
job. The Publisher node contains all repositories for all customer
projects. It is configured as a Jenkins slave. The repositories are
maintained by native tools of their respective distribution
(reprepro or createrepo).

The Publisher slave is fully private and available from Jenkins Master
node only because of containing a GPG key. All the packages and
repositories are signed in terms of their respective distribution by
GPG keys that are stored on the Publisher node.

**Publishing stage**:

#. Getting built packages from the build host (over ``scp``).
#. Checking if packages can be added to a repository (version checking
   against existing packages in order to prevent downgrading).
#. Signing new packages (all ``.rpm`` and source ``.deb``) with GPG keys.
#. Removing existing and adding new packages to a repository.
#. Resigning the repository metadata.
#. Syncing new repository state to a Mirror host (over ``rsync``).

Mirror node
~~~~~~~~~~~

All repositories are available through http or rsync protocols and are
synced by a Publisher to a Mirror host.