Devops Guide
============

Introduction
------------

Fuel-Devops is a sublayer between application and target environment (currently
only supported under libvirt).


This application is used for testing purposes like grouping virtual machines to
environments, booting KVM VMs locally from the ISO image and over the network
via PXE, creating, snapshotting and resuming back the whole environment in
single action, create virtual machines with multiple NICs, multiple hard drives
and many other customizations with a few lines of code in system tests.

After 6.0 release, fuel-devops was divided into 2.5.x and 2.9.x versions. Two
separate versions of fuel-devops provide backward compatibility for system
tests which have been refactored since the last major release. `How to migrate`_

For sources please refer to
`fuel-devops repository on github <https://github.com/openstack/fuel-devops>`_.

.. _install system dependencies:

Installation
-------------

The installation procedure can be implemented via PyPI in Python virtual environment
(suppose you are using *Ubuntu 12.04* or *Ubuntu 14.04*):

Before using it, please install the following required dependencies:

.. code-block:: bash

    sudo apt-get install git \
    postgresql \
    postgresql-server-dev-all \
    libyaml-dev \
    libffi-dev \
    python-dev \
    python-libvirt \
    python-pip \
    qemu-kvm \
    qemu-utils \
    libvirt-bin \
    libvirt-dev \
    ubuntu-vm-builder \
    bridge-utils

    sudo apt-get update && sudo apt-get upgrade -y

.. _DevOpsPyPIvenv:

Devops installation in `virtualenv <http://virtualenv.readthedocs.org/en/latest/>`_
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Install packages needed for building python eggs

.. code-block:: bash

    sudo apt-get install python-virtualenv libpq-dev libgmp-dev

2. In case you are using *Ubuntu 12.04* let's update pip and virtualenv, otherwise you can skip this step

.. code-block:: bash

    sudo pip install pip virtualenv --upgrade
    hash -r

4. Create virtualenv for the *devops* project

.. code-block:: bash

    virtualenv --system-site-packages <path>/fuel-devops-venv

.. note:: If you want to use different devops versions in the same time, you can create several different folders for each version, and then activate required virtual environment for each case.
    For example: ::
    virtualenv --system-site-packages <path>/fuel-devops-venv        # For fuel-devops 2.5.x
    virtualenv --system-site-packages <path>/fuel-devops-venv-2.9    # For fuel-devops 2.9.x

<path> represents the path where your Python virtualenv will be located. (e.g. ~/venv). If it is not specified, it will use the current working directory.

5. Activate virtualenv and install *devops* package using PyPI.

.. code-block:: bash

    source  <path>/fuel-devops-venv/bin/activate
    pip install git+https://github.com/openstack/fuel-devops.git@<version> --upgrade

where <version> is the specific version of fuel-devops you would like to
install. For Fuel 6.0 and earlier, take the latest fuel-devops 2.5.x. For Fuel
6.1 and later, use 2.9.x or newer. See more information on the latest available
versions in `fuel-devops <https://github.com/openstack/fuel-devops/tags>`_
repo.

setup.py in fuel-devops repository does everything required.

.. hint:: You can also use
    `virtualenvwrapper <http://virtualenvwrapper.readthedocs.org/>`_
    which can help you manage virtual environments

6. Next, follow :ref:`DevOpsConf` section

.. _DevOpsConf:

Configuration
--------------

Basically *devops* requires that the following system-wide settings are
configured:

 * Default libvirt storage pool is active (called 'default')
 * Current user must have permission to run KVM VMs with libvirt
 * PostgreSQL server running with appropriate grants and schema for *devops*
 * [Optional] Nested Paging is enabled

Configuring libvirt pool
~~~~~~~~~~~~~~~~~~~~~~~~~

Create libvirt's pool

.. code-block:: bash

    sudo virsh pool-define-as --type=dir --name=default --target=/var/lib/libvirt/images
    sudo virsh pool-autostart default
    sudo virsh pool-start default

Permissions to run KVM VMs with libvirt with current user
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Give current user permissions to use libvirt (Do not forget to log out and log back in!)

.. code-block:: bash

    sudo usermod $(whoami) -a -G libvirtd,sudo

Configuring Postgresql database
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Set local peers to be trusted by default, create user and db and load fixtures.

.. code-block:: bash

    sudo sed -ir 's/peer/trust/' /etc/postgresql/9.*/main/pg_hba.conf
    sudo service postgresql restart
    sudo -u postgres createuser -P <user> # see default <user> and <db> below
    sudo -u postgres createdb <db> -O <user>
    django-admin.py syncdb --settings=devops.settings
    django-admin.py migrate devops --settings=devops.settings

* in 2.5.x version, default <user> and <db> are **devops**
* in 2.9.x version, default <user> and <db> are **fuel_devops**

.. note:: Depending on your Linux distribution,
    `django-admin <http://django-admin-tools.readthedocs.org>`_ may refer
    to system-wide django installed from package. If this happens you could get
    an exception that says that devops.settings module is not resolvable.
    To fix this, run django-admin.py (or django-admin) with a relative path ::

    ./bin/django-admin syncdb --settings=devops.settings
    ./bin/django-admin migrate devops --settings=devops.settings


[Optional] Enabling `Nested Paging <http://en.wikipedia.org/wiki/Second_Level_Address_Translation>`_
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This option is enabled by default in the KVM kernel module

.. code-block:: bash

    $ cat /etc/modprobe.d/qemu-system-x86.conf
    options kvm_intel nested=1

In order to be sure that this feature is enabled on your system,
please run:

.. code-block:: bash

    sudo kvm-ok && cat /sys/module/kvm_intel/parameters/nested

The result should be:

.. code-block:: bash

    INFO: /dev/kvm exists
    KVM acceleration can be used
    Y


Environment creation via Devops + Fuel_QA or Fuel_main
-------------------------------------------------------

Depending on the Fuel release, you may need a different repository. In case of
6.0 or earlier, please use *fuel-main* repository. For 6.1 and later, the
*fuel-qa* is required.

1. Clone GIT repository

.. code-block:: bash

    git clone https://github.com/openstack/fuel-qa # fuel-main for 6.0 and earlier
    cd fuel-qa/

2. Install requirements

.. code-block:: bash

   source <path>/fuel-devops-venv/bin/activate
   pip install -r ./fuelweb_test/requirements.txt --upgrade

3. Check :ref:`DevOpsConf` section

4. Prepare environment

Download Fuel ISO from
`Nightly builds <https://ci.fuel-infra.org/view/ISO/>`_
or build it yourself (please, refer to :ref:`building-fuel-iso`)

Next, you need to define several variables for the future environment

.. code-block:: bash

    export ISO_PATH=<path_to_iso>
    export NODES_COUNT=<number_nodes>

Optionally you can specify the name of your test environment (it will
be used as a prefix for the domains and networks names created by
libvirt, defaults is =fuel_system_test=)

.. code-block:: bash

    export ENV_NAME=<name_of_env>

.. code-block:: bash

    export VENV_PATH=<path>/fuel-devops-venv

If you want to use separated files for snapshots you need to use libvirtd in version >= 1.2.12
and set env variable. This change will switch snapshots created by libvirt from internal
to external mode.

.. code-block:: bash

    export SNAPSHOTS_EXTERNAL=true

.. note:: External snapshots by default uses ~/.devops/snap directory to store memory dumps.
   If you want to use other directory you can set SNAPSHOTS_EXTERNAL_DIR variable.

   .. code-block:: bash

      export SNAPSHOTS_EXTERNAL_DIR=~/.devops/snap

Alternatively, you can edit this file to set them as a default values

.. code-block:: bash

    fuelweb_test/settings.py

Start tests by running this command

.. code-block:: bash

    ./utils/jenkins/system_tests.sh -t test -w $(pwd) -j fuelweb_test -i $ISO_PATH -o --group=setup

For more information about how tests work, read the usage information

.. code-block:: bash

    ./utils/jenkins/system_tests.sh -h

Important notes for Sahara tests
--------------------------------
 * It is not recommended to start tests without KVM.
 * For the best performance Put Sahara image
   `savanna-0.3-vanilla-1.2.1-ubuntu-13.04.qcow2 <http://sahara-files.mirantis.com/savanna-0.3-vanilla-1.2.1-ubuntu-13.04.qcow2>`_
   (md5: 9ab37ec9a13bb005639331c4275a308d) in /tmp/ before start, otherwise
   (If Internet access is available) the image will download automatically.

Important notes for Murano tests
--------------------------------
 * Murano is deprecated in Fuel 9.0.
 * Put Murano image `ubuntu-murano-agent.qcow2 <http://sahara-files.mirantis.com/ubuntu-murano-agent.qcow2>`_
   (md5: b0a0fdc0b4a8833f79701eb25e6807a3) in /tmp before start.
 * Running Murano tests on instances without an Internet connection will fail.
 * For Murano tests execute 'export SLAVE_NODE_MEMORY=5120' before starting.
 * If you need an image For Heat autoscale tests check
   `prebuilt-jeos-images <https://fedorapeople.org/groups/heat/prebuilt-jeos-images/>`_.

Run single OSTF tests several times
-----------------------------------
 * Export environment variable OSTF_TEST_NAME. Example: export OSTF_TEST_NAME='Request list of networks'
 * Export environment variable OSTF_TEST_RETRIES_COUNT. Example: export OSTF_TEST_RETRIES_COUNT=120
 * Execute test_ostf_repetable_tests from tests_strength package

Run tests ::

       sh "utils/jenkins/system_tests.sh" -t test \
            -w $(pwd) \
            -j "fuelweb_test" \
            -i "$ISO_PATH" \
            -V $(pwd)/venv/fuelweb_test \
            -o \
            --group=create_delete_ip_n_times_nova_flat

.. _How to migrate:

Upgrade from system-wide devops to devops in Python virtual environment
------------------------------------------------------------------------

To migrate from older devops, follow these steps:

1. Remove system-wide fuel-devops (e.g. python-devops)

You must remove system-wide fuel-devops and switch to separate venvs with
different versions of fuel-devops, for Fuel 6.0.x (and older) and 6.1 release.

Repositories 'fuel-main' and 'fuel-qa', that contain system tests, must use different Python virtual environments, for example:

* ~/venv-nailgun-tests - used for 6.0.x and older releases. Contains version 2.5.x of fuel-devops
* ~/venv-nailgun-tests-2.9 - used for 6.1 and above. Contains version 2.9.x of fuel-devops

If you have scripts which use system fuel-devops, fix them, and activate Python
venv before you start working in your devops environment.

By default, the network pool is configured as follows:

* 10.108.0.0/16 for devops 2.5.x
* 10.109.0.0/16 for 2.9.x

Please check other settings in *devops.settings*, especially the connection settings to the database.

Before using devops in Python venv, you need to `install system dependencies`_

2. Update fuel-devops and Python venv on CI servers

To update fuel-devops, you can use the following examples:

.. code-block:: bash

    # DevOps 2.5.x for system tests from 'fuel-main' repository
    if [ -f ~/venv-nailgun-tests/bin/activate ]; then
      echo "Python virtual env exist"
    else
      rm -rf ~/venv-nailgun-tests
      virtualenv --system-site-packages  ~/venv-nailgun-tests
    fi
    source ~/venv-nailgun-tests/bin/activate
    pip install -r https://raw.githubusercontent.com/openstack/fuel-main/master/fuelweb_test/requirements.txt --upgrade
    django-admin.py syncdb --settings=devops.settings --noinput
    django-admin.py migrate devops --settings=devops.settings --noinput
    deactivate

    # DevOps 2.9.x for system tests from 'fuel-qa' repository
    if [ -f ~/venv-nailgun-tests-2.9/bin/activate ]; then
      echo "Python virtual env exist"
    else
      rm -rf ~/venv-nailgun-tests-2.9
      virtualenv --system-site-packages  ~/venv-nailgun-tests-2.9
    fi
    source ~/venv-nailgun-tests-2.9/bin/activate
    pip install -r https://raw.githubusercontent.com/openstack/fuel-qa/master/fuelweb_test/requirements.txt --upgrade
    django-admin.py syncdb --settings=devops.settings --noinput
    django-admin.py migrate devops --settings=devops.settings --noinput
    deactivate

3. Setup new repository of system tests for 6.1 release

All system tests for 6.1 and higher were moved to
`fuel-qa <https://github.com/openstack/fuel-qa>`_ repo.

To upgrade 6.1 jobs, follow these steps:

* make a separate Python venv, for example in ~/venv-nailgun-tests-2.9
* install `requirements <https://github.com/openstack/fuel-qa/blob/master/fuelweb_test/requirements.txt>`_ of system tests
* if you are using system tests on CI, please configure your CI to use new Python venv, or export path to the new Python venv in the variable VENV_PATH:
  export VENV_PATH=<path>/fuel-devops-venv-2.9

Known issues
------------
* Some versions of libvirt contain a bug that breaks QEMU virtual machine
  XML. You can see this when tests crush with a *libvirt: QEMU Driver error:
  unsupported configuration: host doesn't support invariant TSC*. See: `Bug 1133155 <https://bugzilla.redhat.com/show_bug.cgi?id=1133155>`_.

  Workaround: upgrade libvirt to the latest version.
