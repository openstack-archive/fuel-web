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

After 6.0 release, fuel-devops was divided into 2.5.x and 2.9.x versions.

For sources please refer to
`fuel-devops repository on github <https://github.com/stackforge/fuel-devops>`_.

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

Devops installation in `virtualenv <http://virtualenv.readthedocs.org/en/latest/virtualenv.html>`_
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Installation procedure is the same as in the case of :ref:`DevOpsPyPI`,
but we should also configure virtualenv

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

<path> represents the path where your Python virtualenv will be located. (e.g. ~/venv). If it is not specified, it will use the current working directory.

5. Activate virtualenv and install *devops* package using PyPI.

.. code-block:: bash

    source  <path>/fuel-devops-venv/bin/activate
    pip install git+https://github.com/stackforge/fuel-devops.git@<version> --upgrade

where <version> is the specific version of fuel-devops you would like to install

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

Set local peers to be trusted by default, create user and db and load fixtures

.. code-block:: bash

    sudo sed -ir 's/peer/trust/' /etc/postgresql/9.*/main/pg_hba.conf
    sudo service postgresql restart
    sudo -u postgres createuser -P <user> # set password the same as user name
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
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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

Depending on the Fuel release, you may need a different repository. In case of 6.0 or earlier, please use *fuel-main* repository. For 6.1 and below, the *fuel-qa* is required.

1. Clone GIT repository

.. code-block:: bash

    git clone https://github.com/stackforge/fuel-qa # fuel-main for 6.0 and earlier
    cd fuel-qa/

2. Install requirements

.. code-block:: bash

   source <path>/fuel-devops-venv/bin/activate
   pip install -r ./fuelweb_test/requirements.txt --upgrade

3. Check :ref:`DevOpsConf` section

4. Prepare environment

Download Fuel ISO from
`Nightly builds <https://fuel-jenkins.mirantis.com/view/ISO/>`_
or build it yourself (please, refer to :ref:`building-fuel-iso`)

Next, you need to define several variables for the future environment

.. code-block:: bash

    export ISO_PATH=<path_to_iso>
    export NODES_COUNT=<number_nodes>
    export ENV_NAME=<name_of_env>

.. code-block:: bash

    export VENV_PATH=<path>/fuel-devops-venv

Alternatively, you can edit this file to set them as a default values

.. code-block:: bash

    fuelweb_test/settings.py

Start tests by running this command

.. code-block:: bash

    ./utils/jenkins/system_tests.sh -t test -w $(pwd) -j fuelweb_test -i $ISO_PATH -o --group=setup

For more information about how tests work, read the usage information

.. code-block:: bash

    ./utils/jenkins/system_tests.sh -h

Important notes for Sahara and Murano tests
--------------------------------------------
 * It is not recommended to start tests without KVM.
 * For the best performance Put Sahara image
   `savanna-0.3-vanilla-1.2.1-ubuntu-13.04.qcow2 <http://sahara-files.mirantis.com/savanna-0.3-vanilla-1.2.1-ubuntu-13.04.qcow2>`_
   (md5: 9ab37ec9a13bb005639331c4275a308d) in /tmp/ before start, otherwise
   (If Internet access is available) the image will download automatically.
 * Put Murano image `ubuntu-murano-agent.qcow2 <http://sahara-files.mirantis.com/ubuntu-murano-agent.qcow2>`_
   (md5: b0a0fdc0b4a8833f79701eb25e6807a3) in /tmp before start.
 * Running Murano tests on instances without an Internet connection will fail.
 * For Murano tests execute 'export SLAVE_NODE_MEMORY=5120' before starting.
 * Heat autoscale tests require the image
   `F17-x86_64-cfntools.qcow2 <https://fedorapeople.org/groups/heat/prebuilt-jeos-images/F17-x86_64-cfntools.qcow2>`_
   (md5: afab0f79bac770d61d24b4d0560b5f70) be placed in /tmp before starting.

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


Upgrade from system-wide devops to devops in Python virtual environment
------------------------------------------------------------------------

To migrate from older devops, follow these steps:

1. Remove system-wide fuel-devops (e.g. python-devops)

You must remove system-wide fuel-devops and start using separate repositories and different versions of fuel-devops, for Fuel 6.0.x (and older) and 6.1 release.

Each repository of system tests must use different Python venv which is placed in Jenkins slave home:
* ~jenkins/venv-nailgun-tests - used for 6.0.x and older releases. Contains version 2.5.x of fuel-devops
* ~jenkins/venv-nailgun-tests-2.9 - used for 6.1 and above. Contains version 2.9.x of fuel-devops

If you have scripts which use system fuel-devops, fix them, and activate Python venv before you start working in your devops environment.

By default, the network pool is configured as follows:
* 10.108.0.0/16 for devops 2.5.x
* 10.109.0.0/16 for 2.9.x

Please check other settings in *devops.settings*.

Before using devops in Python venv, you need to install system dependencies, see :ref:`Installation` for more details.

2. Update fuel-devops and Python venv on CI servers

To update devops, you can use Jenkins jobs:

.. code-block:: bash

    # DevOps 2.5.x
    if [ -f /home/jenkins/venv-nailgun-tests/bin/activate ]; then
      source /home/jenkins/venv-nailgun-tests/bin/activate
      echo "Python virtual env exist"
      pip install -r https://raw.githubusercontent.com/stackforge/fuel-main/master/fuelweb_test/requirements.txt --upgrade
      django-admin.py syncdb --settings=devops.settings --noinput
      django-admin.py migrate devops --settings=devops.settings --noinput
      deactivate
    else
      rm -rf /home/jenkins/venv-nailgun-tests
      virtualenv --system-site-packages  /home/jenkins/venv-nailgun-tests
      source /home/jenkins/venv-nailgun-tests/bin/activate
      pip install -r https://raw.githubusercontent.com/stackforge/fuel-main/master/fuelweb_test/requirements.txt --upgrade
      django-admin.py syncdb --settings=devops.settings --noinput
      django-admin.py migrate devops --settings=devops.settings --noinput
      deactivate
    fi

    # DevOps 2.9.x
    if [ -f /home/jenkins/venv-nailgun-tests-2.9/bin/activate ]; then
      source /home/jenkins/venv-nailgun-tests-2.9/bin/activate
      echo "Python virtual env exist"
      pip install -r https://raw.githubusercontent.com/stackforge/fuel-qa/master/fuelweb_test/requirements.txt --upgrade
      django-admin.py syncdb --settings=devops.settings --noinput
      django-admin.py migrate devops --settings=devops.settings --noinput
      deactivate
    else
      rm -rf /home/jenkins/venv-nailgun-tests-2.9
      virtualenv --system-site-packages  /home/jenkins/venv-nailgun-tests-2.9
      source /home/jenkins/venv-nailgun-tests-2.9/bin/activate
      pip install -r https://raw.githubusercontent.com/stackforge/fuel-qa/master/fuelweb_test/requirements.txt --upgrade
      django-admin.py syncdb --settings=devops.settings --noinput
      django-admin.py migrate devops --settings=devops.settings --noinput
      deactivate
    fi

3. Setup new repository of system tests for 6.1 release

All system tests for 6.1 and higher were moved to https://github.com/stackforge/fuel-qa repo.

To upgrade 6.1 jobs, follow these steps:
* make a separate Python venv, for example in ~jenkins/venv-nailgun-tests-2.9
* install requirements of system tests from https://github.com/stackforge/fuel-qa/blob/master/fuelweb_test/requirements.txt
* update 6.1 jobs for using new Python venv
* on our CI, we use VEVN_PATH environment varible to select Python venv
