.. _buildsystem:


Fuel ISO build system
=====================

Use the `fuel-main repository <https://github.com/openstack/fuel-main.git>`_
to build Fuel components such as an ISO or an upgrade tarball.
This repository contains a set of GNU Make build scripts.

Quick start
-----------

1. You must use Ubuntu 14.04 distribution to build Fuel components or the build process may fail. Note that build only works for x64 platforms.

2. Check whether you have git installed in
   your system. To do that, use the following command:

::

   which git

If git is not found, install it with the following command:

::


   apt-get install git


3. Clone the **fuel-main** git repository to the location where
   you will work. The root of your repo will be named `fuel-main`.
   In this example, it will be located under the *~/fuel* directory:

::

   mkdir ~/fuel
   cd ~/fuel
   git clone https://github.com/openstack/fuel-main.git
   cd fuel-main


.. note::Fuel build system consists of the following components:

       * a shell script (**./prepare-build-env.sh**) - prepares the build environment by checking
          that all necessary packages are installed and installing any that are not.

       * **fuel-main** directory - the only one required repository for building the Fuel ISO.

       The make script then downloads the additional components
       (Fuel Library, Nailgun, Astute and OSTF).
       Unless otherwise specified in the makefile,
       the master branch of each respective repo is used to build the ISO.

4. Run the shell script:

::

   ./prepare-build-env.sh

  and wait until **prepare-build-env.sh**
  installs the Fuel build evironment on your computer.

5. After the script runs successfully, issue the following command to build a
   Fuel ISO:

::

   make iso

6. Use the following command to list the available make targets:

::

   make help

For the full list of available targets with description, see :ref:`Build targets <build-targets>` section below.

Build system structure
----------------------

Fuel consists of several components such as web interface,
puppet modules, orchestration components, testing components.
Source code of all those components is split into multiple git
repositories like, for example:

- https://github.com/openstack/fuel-web
- https://github.com/openstack/fuel-ui
- https://github.com/openstack/fuel-astute
- https://github.com/openstack/fuel-ostf
- https://github.com/openstack/fuel-library
- https://github.com/openstack/fuel-docs

The main component of the Fuel build system is
*fuel-main* directory.

Fuel build processes are quite complicated,
so to make the **fuel-main** code easily
maintainable, it is
split into a bunch of files and directories.

Those files
and directories contain independent
(or at least almost independent)
pieces of Fuel build system:

* **Makefile** - the main Makefile which includes all other make modules.

* **config.mk** - contains parameters used to customize the build process,
  specifying items such as build paths,
  upstream mirrors, source code repositories
  and branches, built-in default Fuel settings and ISO name.

* **rules.mk** - defines frequently used macros.

* **repos.mk** - contains make scripts to download the
  other repositories to develop Fuel
  components put into separate repos.

* **sandbox.mk** - shell script definitions that create
  and destroy the special chroot environment required to
  build some components.
  For example, for building RPM packages,
  CentOS images we use CentOS chroot environment.

* **mirror** - contains the code which is used to download
  all necessary packages from upstream mirrors and build new
  ones which are to be copied on Fuel ISO even if Internet
  connection is down.

* **packages** - contains DEB and RPM
  specs as well as make code for building those packages,
  included in Fuel DEB and RPM mirrors.

* **bootstrap** -  contains a make script intended
  to build CentOS-based miniroot image (a.k.a initrd or initramfs).

* **docker** - contains the make scripts to
  build docker containers, deployed on the Fuel Master node.

* **iso** - contains **make** scripts for building Fuel ISO file.


.. _build-targets:

Build targets
-------------

* **all** - used for building all Fuel artifacts.
  Currently, it is an alias for **iso** target.

* **bootstrap** - used for building in-memory bootstrap
  image which is used for auto-discovering.

* **mirror** - used for building local mirrors (the copies of CentOS and
  Ubuntu mirrors which are then placed into Fuel ISO).
  They contain all necessary packages including those listed in
  *requirements-*.txt* files with their dependencies as well as those which
  are Fuel packages. Packages listed in *requirements-*.txt* files are downloaded
  from upstream mirrors while Fuel packages are built from source code.

* **iso** - used for building Fuel ISO. If build succeeds,
  ISO is put into build/artifacts folder.

* **clean** - removes build directory.

* **deep_clean** - removes build directory and local mirror.
  Note that if you remove a local mirror, then next time
  the ISO build job will download all necessary packages again.
  So, the process goes faster if you keep local mirrors.
  You should also mind the following:
  it is better to run *make deep_clean* every time when building an ISO to make sure the local mirror is consistent.


Customizing build process
-------------------------

There are plenty of variables in make files.
Some of them represent a kind of build parameters.
They are defined in **config.mk** file:

* **TOP_DIR** -  a default current directory.
  All other build directories are relative to this path.

* **BUILD_DIR** - contains all files, used during build process.
  By default, it is **$(TOP_DIR)/build**.

* **ARTS_DIR** - contains build artifacts such as ISO and IMG files
  By default, it is **$(BUILD_DIR)/artifacts**.

* **LOCAL_MIRROR** - contains local CentOS and Ubuntu mirrors
  By default, it is **$(TOP_DIR)/local_mirror**.

* **DEPS_DIR** - contains build targets that depend on artifacts
  of the previous build jobs, placed there
  before build starts. By default, it is **$(TOP_DIR)/deps**.

* **ISO_NAME** - a name of Fuel ISO without file extension:
  if **ISO_NAME** = **MY_CUSTOM_NAME**, then Fuel ISO file will
  be placed into **$(MY_CUSTOM_NAME).iso**.

* **ISO_PATH** - used to specify Fuel ISO full path instead of defining
  just ISO name.
  By default, it is **$(ARTS_DIR)/$(ISO_NAME).iso**.

* Fuel ISO contains some default settings for the
  Fuel Master node. These settings can be customized
  during Fuel Master node installation.
  One can customize those
  settings using the following variables:

- **MASTER_IP** - the Fuel Master node IP address.
  By default, it is 10.20.0.2.

- **MASTER_NETMASK** - Fuel Master node IP netmask.
  By default, it is 255.255.255.0.

- **MASTER_GW** - Fuel Master node default gateway.
  By default, it is is 10.20.0.1.

- **MASTER_DNS** -  the upstream DNS location for the Fuel master node.
  FUel Master node DNS will redirect there all DNS requests that it is not able to resolve itself.
  By default, it is 10.20.0.1.


Other options
-------------

* **[repo]_REPO** - remote source code repo.
  URL or git repository can be specified for each of the Fuel components.
  (FUELLIB, NAILGUN, ASTUTE, OSTF).

* **[repo]_COMMIT** - source branch for each of the Fuel components to build.

* **[repo]_GERRIT_URL** - gerrit repo.

* **[repo]_GERRIT_COMMIT** - list of extra commits from gerrit.

* **[repo]_SPEC_REPO** - repo for RPM/DEB specs of OpenStack packages.

* **[repo]_SPEC_COMMIT** - branch for checkout.

* **[repo]_SPEC_GERRIT_URL** - gerrit repo for OpenStack specs.

* **[repo]_SPEC_GERRIT_COMMIT** - list of extra commits from gerrit for specs.

* **USE_MIRROR** - pre-built mirrors from Fuel infrastructure.
  The following mirrors can be used:
  * ext (external mirror, available from outside of Mirantis network)
  * none (reserved for building local mirrors: in this case
  CentOS and Ubuntu packages will be fetched from upstream mirrors, so
  that it will make the build process much slower).

* **MIRROR_CENTOS** - download CentOS packages from a specific remote repo.

* **MIRROR_UBUNTU** - download Ubuntu packages from a specific remote repo.

* **MIRROR_DOCKER** - download docker images from a specific remote url.

* **EXTRA_RPM_REPOS** - extra repos with RPM packages.
  Each repo must be comma separated
  tuple with repo-name and repo-path:
  <first_repo_name>,<repo_path> <second_repo_name>,<second_repo_path>
  For example,
  *qemu2,http://osci-obs.vm.mirantis.net:82/centos-fuel-5.1-stable-15943/centos/ libvirt,http://osci-obs.vm.mirantis.net:82/centos-fuel-5.1-stable-17019/centos/*.

Note that if you want to add more packages to the Fuel Master node, you should update the **requirements-rpm.txt** file.
