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

For sources please refer to
`fuel-devops repository on github <https://github.com/stackforge/fuel-devops>`_.

Installation
-------------

The installation procedure can be implemented in two different ways
(suppose you are using *Ubuntu 12.04* or *Ubuntu 14.04*):

* from :ref:`deb packages <DevOpsApt>` (using apt)
* from :ref:`python packages <DevOpsPyPI>` (using PyPI) (also in :ref:`virtualenv <DevOpsPyPIvenv>`)

Each of the above approaches is described in detail below.

.. _DevOpsApt:

Devops installation from packages
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Checking and applying latest updates

.. code-block:: bash

    sudo apt-get update && sudo apt-get upgrade -y

2. Installing dependencies

.. code-block:: bash

    sudo apt-get install postgresql \
    git \
    python-pip \
    python-psycopg2 \
    python-ipaddr \
    python-libvirt \
    python-paramiko \
    python-django \
    python-django-south \
    python-ipaddr \
    python-yaml \
    python-mock

.. note:: Depending on your Linux distribution some of the above packages may
    not exists in your upstream repositories. In this case, please exclude
    them from the installation list and repeat *step 2*. Missing packages will
    be installed by python (from PyPI) during the next step

3. Clone `fuel-devops <https://github.com/stackforge/fuel-devops>`_ repo and run setup.py

.. code-block:: bash

    git clone git://github.com/stackforge/fuel-devops.git
    cd fuel-devops
    sudo python ./setup.py install

4. Now we can check that *devops* has been installed successfully

.. code-block:: bash

    user@host:~$ pip list

    apt-xapian-index (0.44)
    argparse (1.2.1)
    chardet (2.0.1)
    command-not-found (0.2.44)
    devops (2.4.2)
    distribute (0.6.24dev-r0)
    Django (1.6.5)
    GnuPGInterface (0.3.2)
    ipaddr (2.1.10)
    language-selector (0.1)
    mock (0.7.2)
    paramiko (1.7.7.1)
    pip (1.5.6)
    psycopg2 (2.4.5)
    pycrypto (2.4.1)
    python-apt (0.8.3ubuntu7.2)
    python-debian (0.1.21ubuntu1)
    PyYAML (3.10)
    setuptools (0.6c11)
    South (0.7.3)
    ufw (0.31.1-1)
    wsgiref (0.1.2)
    xmlbuilder (1.0)

.. note:: In case of **pip: error: No command by the name pip list**,
    please update pip (related to *Ubuntu 12.04 LTS*)
    ::

        sudo pip install pip --upgrade
        hash -r

5. Next, follow :ref:`DevOpsConf` section

.. _DevOpsPyPI:

Devops installation using `PyPI <https://pypi.python.org/pypi>`_
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The installation procedure should be implemented by following the next steps:

1. Checking and applying latest updates

.. code-block:: bash

    sudo apt-get update && sudo apt-get upgrade -y

2. Install packages needed for building python eggs and working with *devops* (postgresql, git)

.. code-block:: bash

    sudo apt-get install git \
    postgresql \
    python-dev \
    python-pip \
    python-libvirt \
    libyaml-dev \
    libpq-dev \
    libgmp-dev

3. In case you are using *Ubuntu 12.04* let's update pip, otherwise you can skip this step

.. code-block:: bash

    sudo pip install pip --upgrade
    hash -r

4. Install *devops* package using python setup tools. Clone `fuel-devops <https://github.com/stackforge/fuel-devops>`_ and run setup.py

.. code-block:: bash

    git clone git://github.com/stackforge/fuel-devops.git
    cd fuel-devops
    sudo python ./setup.py install

5. Next, follow :ref:`DevOpsConf` section

.. _DevOpsPyPIvenv:

Devops installation in `virtualenv <http://virtualenv.readthedocs.org/en/latest/virtualenv.html>`_
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Installation procedure is the same as in the case of :ref:`DevOpsPyPI`,
but we should also configure virtualenv

1. Checking and applying latest updates

.. code-block:: bash

    sudo apt-get update && sudo apt-get upgrade -y

2. Install packages needed for building python eggs and working with *devops* (postgresql, git, virtualenv)

.. code-block:: bash

    sudo apt-get install git \
    postgresql \
    python-dev \
    python-pip \
    python-libvirt \
    python-virtualenv \
    libyaml-dev \
    libpq-dev \
    libgmp-dev

3. In case you are using *Ubuntu 12.04* let's update pip and virtualenv, otherwise you can skip this step

.. code-block:: bash

    sudo pip install pip virtualenv --upgrade
    hash -r

4. Create virtualenv for the *devops* project

.. code-block:: bash

    virtualenv --system-site-packages devops-venv

5. Activate virtualenv and install *devops* package using python setup tools

.. code-block:: bash

    . devops-venv/bin/activate
    pip install git+https://github.com/stackforge/fuel-devops.git --upgrade

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

Give current user permissions to use libvirt

.. code-block:: bash

    sudo usermod $(whoami) -a -G libvirtd,sudo

Configuring Postgresql database
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Set local peers to be trusted by default and load fixtures

.. code-block:: bash

    sudo sed -ir 's/peer/trust/' /etc/postgresql/9.*/main/pg_hba.conf
    sudo service postgresql restart
    django-admin.py syncdb --settings=devops.settings
    django-admin.py migrate devops --settings=devops.settings

.. note:: Depending on your Linux distribution,
    `django-admin.py <http://django-admin-tools.readthedocs.org>`_ may refer
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


Environment creation via Devops + Fuel_main
-------------------------------------------

1. Install basic packages

.. code-block:: bash

    sudo apt-get install -y libxslt1-dev libffi-dev


2. Clone fuel-main

.. code-block:: bash

    git clone https://github.com/stackforge/fuel-main
    cd fuel-main/

3. Install requirements

.. code-block:: bash

    . devops-venv/bin/activate
    pip install -r ./fuelweb_test/requirements.txt --upgrade

4. Prepare environment

Download Fuel ISO from
`Nightly builds <https://fuel-jenkins.mirantis.com/view/ISO/>`_
or build it yourself (please, refer to :ref:`building-fuel-iso`)

Next, you need to define several variables for the future environment

.. code-block:: bash

    export ISO_PATH=<path_to_iso>
    export NODES_COUNT=<number_nodes>
    export ENV_NAME=<name_of_env>
    export VENV_PATH=<path_to_virtualenv>

Alternatively, you can edit this file to set them as a default values

.. code-block:: bash

    fuelweb_test/settings.py

Start tests by running this command

.. code-block:: bash

    export PYTHONPATH=$(pwd)
    ./utils/jenkins/system_tests.sh -t test -w $(pwd) -j fuelweb_test -i $ISO_PATH -o --group=setup

For more information about how tests work, read the usage information

.. code-block:: bash

    ./utils/jenkins/system_tests.sh -h

Important notes for Savanna and Murano tests
--------------------------------------------
 * It is not recommended to start tests without KVM.
 * Put Savanna image savanna-0.3-vanilla-1.2.1-ubuntu-13.04.qcow2 (md5 9ab37ec9a13bb005639331c4275a308d) in /tmp/ before start for best performance. If Internet access is available, the image will download automatically.
 * Put Murano image cloud-fedora.qcow2 (md5 6e5e2f149c54b898b3c272f11ae31125) in /tmp before start. Murano image available only internally.
 * Murano tests run on instances without an Internet connection will fail.
 * For Murano tests execute 'export SLAVE_NODE_MEMORY=5120' before starting.
 * Heat autoscale tests require the image F17-x86_64-cfntools.qcow2 be placed in /tmp before starting.

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
