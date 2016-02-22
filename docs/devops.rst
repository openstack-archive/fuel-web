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
tests which have been refactored since the last major release. Look here
`how to migrate`_ from older devops.

For sources please refer to
`fuel-devops repository on github <https://github.com/openstack/fuel-devops>`_.

.. _install system dependencies:

Installation
-------------

The installation procedure can be implemented via PyPI in Python virtual
environment (suppose you are using *Ubuntu 12.04* or *Ubuntu 14.04*):

Before using it, please install the following required dependencies:

.. code-block:: bash

    sudo apt-get install --yes \
    git \
    libyaml-dev \
    libffi-dev \
    python-dev \
    python-pip \
    qemu \
    libvirt-bin \
    libvirt-dev \
    vlan \
    bridge-utils \
    genisoimage

    sudo apt-get update && sudo apt-get upgrade -y

.. _DevOpsPyPIvenv:

Devops installation in `virtualenv <http://virtualenv.readthedocs.org/en/latest/virtualenv.html>`_
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Install packages needed for building python eggs

.. code-block:: bash

    sudo apt-get install --yes python-virtualenv libpq-dev libgmp-dev pkg-config

2. In case you are using *Ubuntu 12.04* let's update pip and virtualenv,
   otherwise you can skip this step

.. code-block:: bash

    sudo pip install pip virtualenv --upgrade
    hash -r

3. In oder to store the path where your Python virtualenv will be located
   create your working directory and use the following environment variable. If
   it is not specified, it will use the current working directory:

.. code-block:: bash

     export WORKING_DIR=$HOME/working_dir
     mkdir $HOME/working_dir

4. Create virtualenv for the *devops* project (e.g. ``fuel-devops-venv``).
   Note: the related directory will be used for the ``VENV_PATH`` variable:

.. code-block:: bash

     cd $WORKING_DIR
     sudo apt-get install --yes python-virtualenv
     virtualenv --no-site-packages fuel-devops-venv

.. note:: If you want to use different devops versions in the same time, you
 can create several different folders for each version, and then activate the
 required virtual environment for each case.

    For example::

        virtualenv --no-site-packages fuel-devops-venv        # For fuel-devops 2.5.x
        virtualenv --no-site-packages fuel-devops-venv-2.9    # For fuel-devops 2.9.x

5. Activate virtualenv and install *devops* package using PyPI.
In order to indentify the latest available versions you would like to install,
visit `fuel-devops <https://github.com/openstack/fuel-devops/tags>`_ repo. For
Fuel 6.0 and earlier, take the latest fuel-devops 2.5.x (e.g.
fuel-devops.git@2.5.6). For Fuel 6.1 and later, use 2.9.x or newer (e.g.
fuel-devops.git@2.9.11):

.. code-block:: bash

    . fuel-devops-venv/bin/activate
    pip install git+https://github.com/openstack/fuel-devops.git@2.9.11 --upgrade

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

Give current user permissions to use libvirt: do not forget to log out and log
back in.

.. code-block:: bash

    sudo usermod $(whoami) -a -G libvirtd,sudo

Configuring database
~~~~~~~~~~~~~~~~~~~~~

You can configure PostgreSQL database or as an alternative SQLite.

Configuring PostgreSQL
+++++++++++++++++++++++

Install postgresql package:

.. code-block:: bash

    sudo apt-get install --yes postgresql

Set local peers to be trusted by default, create user and db and load fixtures.

.. code-block:: bash

    pg_version=$(dpkg-query --show --showformat='${version;3}' postgresql)
    pg_createcluster $pg_version main --start
    sudo sed -ir 's/peer/trust/' /etc/postgresql/9.*/main/pg_hba.conf
    sudo service postgresql restart

* in **2.9.x version**, default <user> and <db> are **fuel_devops**

  .. code-block:: bash

      sudo -u postgres createuser -P fuel_devops
      sudo -u postgres psql -c "CREATE ROLE fuel_devops WITH LOGIN PASSWORD 'fuel_devops'"
      sudo -u postgres createdb fuel_devops -O fuel_devops

* in **2.5.x version**, default <user> and <db> are **devops**

  .. code-block:: bash

      sudo -u postgres createuser -P devops
      sudo -u postgres psql -c "CREATE ROLE devops WITH LOGIN PASSWORD 'devops'"
      sudo -u postgres createdb devops -O devops

Configuring SQLite3 database
+++++++++++++++++++++++++++++

Install SQLite3 library:

.. code-block:: bash

    sudo apt-get install --yes libsqlite3-0

Export the path to the SQLite3 database as the database name:

.. code-block:: bash

    export DEVOPS_DB_NAME=$WORKING_DIR/fuel-devops
    export DEVOPS_DB_ENGINE="django.db.backends.sqlite3

Configuring Django
~~~~~~~~~~~~~~~~~~~

After the database setup, we can install the django tables and data:

.. code-block:: bash

    django-admin.py syncdb --settings=devops.settings
    django-admin.py migrate devops --settings=devops.settings

.. note:: Depending on your Linux distribution,
    `django-admin <http://django-admin-tools.readthedocs.org>`_ may refer
    to system-wide django installed from package. If this happens you could get
    an exception that says that devops.settings module is not resolvable.
    To fix this, run django-admin.py (or django-admin) with a relative path ::

    ./bin/django-admin syncdb --settings=devops.settings
    ./bin/django-admin migrate devops --settings=devops.settings


[Optional] Enabling `Nested Paging <http://en.wikipedia.org/wiki/Second_Level_Address_Translation>`_
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The following section covers only Intel platform. This option is enabled by
default in the KVM kernel module. If the file ``qemu-system-x86.conf`` does not
exist, you have to create it.

.. code-block:: bash

    cat /etc/modprobe.d/qemu-system-x86.conf
    options kvm_intel nested=1

In order to be sure that this feature is enabled on your system,
please run:

.. code-block:: bash

    sudo apt-get install --yes cpu-checker
    sudo modprobe kvm_intel
    sudo kvm-ok && cat /sys/module/kvm_intel/parameters/nested

The result should be:

.. code-block:: bash

    INFO: /dev/kvm exists
    KVM acceleration can be used
    Y


Environment creation via Devops + Fuel_QA or Fuel_main
-------------------------------------------------------

Depending on the Fuel release, you may need a different repository.

1. Clone GIT repository

For 6.1 and later, the *fuel-qa* is required:

.. code-block:: bash

    git clone https://github.com/openstack/fuel-qa
    cd fuel-qa/

.. note:: It is recommended to use the stable branch related to the ISO version.
 For instance, with FUEL v7.0 ISO:

   .. code-block:: bash

      git clone https://github.com/openstack/fuel-qa -b stable/7.0

In case of 6.0 or earlier, please use *fuel-main* repository:

.. code-block:: bash

    git clone https://github.com/openstack/fuel-main -b stable/6.0
    cd fuel-main/


2. Install requirements (follow :ref:`DevOpsPyPIvenv` section for the
WORKING_DIR variable)

.. code-block:: bash

   . $WORKING_DIR/fuel-devops-venv/bin/activate
   pip install -r ./fuelweb_test/requirements.txt --upgrade

.. note:: A certain version of fuel-devops is specified in the
 ./fuelweb_test/requirements.txt , so it will overwrite the already installed
 fuel-devops. For example, for fuel-master branch stable/6.0, there is:
    
    .. code-block:: bash

       git+git://github.com/stackforge/fuel-devops.git@2.5.6

 It is recommended to install the django tables and data after installing
 fuel-qa requiremets:

    .. code-block:: bash

        django-admin.py syncdb --settings=devops.settings
        django-admin.py migrate devops --settings=devops.settings

3. Check :ref:`DevOpsConf` section

4. Prepare environment

Download Fuel ISO from
`Nightly builds <https://ci.fuel-infra.org/view/ISO/>`_
or build it yourself (please, refer to :ref:`building-fuel-iso`)

Next, you need to define several variables for the future environment:
 * the path where is located your iso (e.g. $WORKING_DIR/fuel-community-7.0.iso)
 * the number of nodes instantiated for the environment (e.g. 5)

.. code-block:: bash

    export ISO_PATH=$WORKING_DIR/fuel-community-7.0.iso
    export NODES_COUNT=5

Optionally you can specify the name of your test environment (it will
be used as a prefix for the domains and networks names created by
libvirt, defaults is ``fuel_system_test``).

.. code-block:: bash

    export ENV_NAME=fuel_system_test
    export VENV_PATH=$WORKING_DIR/fuel-devops-venv

If you want to use separated files for snapshots you need to set env variable
and use the following required versions:

 * fuel-devops >= 2.9.17
 * libvirtd >= 1.2.12

This change will switch snapshots created by libvirt from internal to external
mode.

.. code-block:: bash

    export SNAPSHOTS_EXTERNAL=true

.. note:: External snapshots by default uses ~/.devops/snap directory to store
 memory dumps. If you want to use other directory you can set
 SNAPSHOTS_EXTERNAL_DIR variable.

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

Repositories 'fuel-main' and 'fuel-qa', that contain system tests, must use
different Python virtual environments, for example:

* ~/venv-nailgun-tests - used for 6.0.x and older releases. Contains version 2.5.x of fuel-devops
* ~/venv-nailgun-tests-2.9 - used for 6.1 and above. Contains version 2.9.x of fuel-devops

If you have scripts which use system fuel-devops, fix them, and activate Python
venv before you start working in your devops environment.

By default, the network pool is configured as follows:

* 10.108.0.0/16 for devops 2.5.x
* 10.109.0.0/16 for 2.9.x

Please check other settings in *devops.settings*, especially the connection
settings to the database.

Before using devops in Python venv, you need to `install system dependencies`_

2. Update fuel-devops and Python venv on CI servers

To update fuel-devops, you can use the following examples:

.. code-block:: bash

    # DevOps 2.5.x for system tests from 'fuel-main' repository
    if [ -f ~/venv-nailgun-tests/bin/activate ]; then
      echo "Python virtual env exist"
    else
      rm -rf ~/venv-nailgun-tests
      virtualenv --no-site-packages ~/venv-nailgun-tests
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
      virtualenv --no-site-packages ~/venv-nailgun-tests-2.9
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
* if you are using system tests on CI, please configure your CI to use new
  Python venv, or export path to the new Python venv in the variable
  ``VENV_PATH`` (follow :ref:`DevOpsPyPIvenv` section for the WORKING_DIR
  variable):

  .. code-block:: bash

      export VENV_PATH=$WORKING_DIR/fuel-devops-venv-2.9


Known issues
------------

* Some versions of libvirt contain a bug that breaks QEMU virtual machine
  XML. You can see this when tests crush with a *libvirt: QEMU Driver error:
  unsupported configuration: host doesn't support invariant TSC*. See:
  `Bug 1133155 <https://bugzilla.redhat.com/show_bug.cgi?id=1133155>`_.

  Workaround: upgrade libvirt to the latest version.

* If the same version of fuel-devops is used with several different databases
  (for example, with multiple sqlite3 databases, or with a separated database for
  each devops in different python virtual environments), there will be a
  collision between Libvirt bridge names and interfaces.

  Workaround: use the same database for the same version of the fuel-devops.

  - for **2.9.x**, export the following env variables:

    .. code-block:: bash

        export DEVOPS_DB_NAME=fuel_devops
        export DEVOPS_DB_USER=fuel_devops
        export DEVOPS_DB_PASSWORD=fuel_devops

  - for **2.5.x**, edit the dict for variable ``DATABASES``:

    .. code-block:: bash      

       vim $WORKING_DIR/fuel-devops-venv/lib/python2.7/site-packages/devops/settings.py


