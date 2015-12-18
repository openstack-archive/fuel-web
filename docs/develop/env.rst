Fuel Development Environment
============================

.. warning:: Fuel ISO build works only on 64-bit operating system.

If you are modifying or augmenting the Fuel source code or if you
need to build a Fuel ISO from the latest branch, you will need
an environment with the necessary packages installed.  This page
lays out the steps you will need to follow in order to prepare
the development environment, test the individual components of
Fuel, and build the ISO which will be used to deploy your
Fuel master node.

The basic operating system for Fuel development is Ubuntu Linux.
The setup instructions below assume Ubuntu 14.04 (64 bit) though most of
them should be applicable to other Ubuntu and Debian versions, too.

Each subsequent section below assumes that you have followed the steps
described in all preceding sections. By the end of this document, you
should be able to run and test all key components of Fuel, build the
Fuel master node installation ISO, and generate documentation.

.. _getting-source:

Getting the Source Code
-----------------------

Source code of OpenStack Fuel can be found at git.openstack.org or
GitHub.

Follow these steps to clone the repositories for each of
the Fuel components:
::

    apt-get install git
    git clone https://github.com/openstack/fuel-main
    git clone https://github.com/openstack/fuel-web
    git clone https://github.com/openstack/fuel-agent
    git clone https://github.com/openstack/fuel-astute
    git clone https://github.com/openstack/fuel-ostf
    git clone https://github.com/openstack/fuel-library
    git clone https://github.com/openstack/fuel-docs


.. _building-fuel-iso:

Building the Fuel ISO
---------------------

The "fuel-main" repository is the only one required in order
to build the Fuel ISO.  The make script then downloads the
additional components (Fuel Library, Nailgun, Astute and OSTF).
Unless otherwise specified in the makefile, the master branch of
each respective repo is used to build the ISO.

The basic steps to build the Fuel ISO from trunk in an
Ubuntu 14.04 environment are:
::

    apt-get install git
    git clone https://github.com/openstack/fuel-main
    cd fuel-main
    ./prepare-build-env.sh
    make iso

If you want to build an ISO using a specific commit or repository,
you will need to modify the "Repos and versions" section in the
config.mk file found in the fuel-main repo before executing "make
iso". For example, this would build a Fuel ISO against the v5.0
tag of Fuel:
::

    # Repos and versions
    FUELLIB_COMMIT?=tags/5.0
    NAILGUN_COMMIT?=tags/5.0
    ASTUTE_COMMIT?=tags/5.0
    OSTF_COMMIT?=tags/5.0

    FUELLIB_REPO?=https://github.com/openstack/fuel-library.git
    NAILGUN_REPO?=https://github.com/openstack/fuel-web.git
    ASTUTE_REPO?=https://github.com/openstack/fuel-astute.git
    OSTF_REPO?=https://github.com/openstack/fuel-ostf.git

To build an ISO image from custom gerrit patches on review, edit the
"Gerrit URLs and commits" section of config.mk, e.g. for
https://review.openstack.org/#/c/63732/8 (id:63732, patch:8) set:
::

   FUELLIB_GERRIT_COMMIT?=refs/changes/32/63732/8

If you are building Fuel from an older branch that does not contain the
"prepare-build-env.sh" script, you can follow these steps to prepare
your Fuel ISO build environment on Ubuntu 14.04:

#. ISO build process requires sudo permissions, allow yourself to run
   commands as root user without request for a password::

    echo "`whoami` ALL=(ALL) NOPASSWD: ALL" | sudo tee -a /etc/sudoers

#. Install software::

    sudo apt-get update
    sudo apt-get install apt-transport-https
    echo deb http://mirror.yandex.ru/mirrors/docker/ docker main | sudo tee /etc/apt/sources.list.d/docker.list
    sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys 36A1D7869245C8950F966E92D8576A8BA88D21E9
    sudo apt-get update
    sudo apt-get install lxc-docker
    sudo apt-get update
    sudo apt-get remove nodejs nodejs-legacy npm
    sudo apt-get install software-properties-common python-software-properties
    sudo add-apt-repository -y ppa:chris-lea/node.js
    sudo apt-get update
    sudo apt-get install build-essential make git ruby ruby-dev rubygems debootstrap createrepo \
    python-setuptools yum yum-utils libmysqlclient-dev isomd5sum \
    python-nose libvirt-bin python-ipaddr python-paramiko python-yaml \
    python-pip kpartx extlinux unzip genisoimage nodejs multistrap \
    lrzip python-daemon
    sudo gem install bundler -v 1.2.1
    sudo gem install builder
    sudo pip install xmlbuilder jinja2
    sudo npm install -g gulp

#. If you haven't already done so, get the source code::

    git clone https://github.com/openstack/fuel-main

#. Now you can build the Fuel ISO image::

    cd fuel-main
    make iso

#. If you encounter issues and need to rebase or start over::

    make clean          #remove build/ directory
    make deep_clean     #remove build/ and local_mirror/

.. note::

  In case you use a virtual machine for building the image, verify the
  following:

    - Both ``BUILD_DIR`` and ``LOCAL_MIRROR`` build directories are
      out of the shared folder path in the `config.mk
      <https://github.com/openstack/fuel-main/blob/master/config.mk>`_
      file. For more information, see:

        - `Shared folders of VitrualBox
          <https://www.virtualbox.org/manual/ch04.html#sharedfolders>`_
          documentation

        - `Synced folders of Vargant
          <https://docs.vagrantup.com/v2/synced-folders/>`_
          documentation

    - To prevent a random docker unexpected termination, a virtual
      machine has a kernel that supports the ``aufs`` file system.

      To install the kernel, run:

      .. code-block:: console

        sudo apt-get install --yes linux-image-extra-virtual

      Reboot the kernel when the installation is complete.  Check that
      docker is using ``aufs`` by running:

      .. code-block:: console

        sudo docker info 2>&1 | grep -q 'Storage Driver: aufs' \
	&& echo OK || echo KO

      For more information, see `Select a storage driver for docker
      <https://docs.docker.com/engine/userguide/storagedriver/selectadriver/>`_.

You can also use the following tools to make your work and development process
with Fuel easier:

* CGenie fuel-utils - a set of tools to interact with code on a Fuel Master node created
  from the ISO. It provides the *fuel* command
  that gives a simple way to upload Python or UI code (with staticfiles compression)
  to Docker containers, SSH into machine and into the container,
  display the logs etc.

* Vagrant SaltStack-based -Vagrant box definition with quick and basic Fuel
  environment with fake tasks.
  This is useful for UI or Nailgun development.

You can download both tools from the
`fuel-dev-tools <https://github.com/openstack/fuel-dev-tools>`_.

Nailgun (Fuel-Web)
------------------

Nailgun is the heart of Fuel project. It implements a REST API as well
as deployment data management. It manages disk volume configuration data,
network configuration data and any other environment specific data
necessary for a successful deployment of OpenStack. It provides the
required orchestration logic for provisioning and
deployment of the OpenStack components and nodes in the right order.
Nailgun uses a SQL database to store its data and an AMQP service to
interact with workers.

Requirements for preparing the nailgun development environment, along
with information on how to modify and test nailgun can be found in
the Nailgun Development Instructions document: :ref:`nailgun-development`


Astute
------

Astute is the Fuel component that represents Nailgun's workers, and
its function is to run actions according to the instructions provided
from Nailgun. Astute provides a layer which encapsulates all the details
about interaction with a variety of services such as Cobbler, Puppet,
shell scripts, etc. and provides a universal asynchronous interface to
those services.

#. Astute can be found in fuel-astute repository

#. Install Ruby dependencies::

    sudo apt-get install git curl
    curl -sSL https://get.rvm.io | bash -s stable
    source ~/.rvm/scripts/rvm
    rvm install 2.1
    rvm use 2.1
    git clone https://github.com/nulayer/raemon.git
    cd raemon
    git checkout b78eaae57c8e836b8018386dd96527b8d9971acc
    gem build raemon.gemspec
    gem install raemon-0.3.0.gem
    cd ..
    rm -Rf raemon

#. Install or update dependencies and run unit tests::

    cd fuel-astute
    ./run_tests.sh

#. (optional) Run Astute MCollective integration test (you'll need to
   have MCollective server running for this to work)::

    cd fuel-astute
    bundle exec rspec spec/integration/mcollective_spec.rb

Running Fuel Puppet Modules Unit Tests
--------------------------------------

If you are modifying any puppet modules used by Fuel, or including
additional modules, you can use the PuppetLabs RSpec Helper
to run the unit tests for any individual puppet module.  Follow
these steps to install the RSpec Helper:

#. Install PuppetLabs RSpec Helper::

    cd ~
    gem2deb puppetlabs_spec_helper
    sudo dpkg -i ruby-puppetlabs-spec-helper_0.4.1-1_all.deb
    gem2deb rspec-puppet
    sudo dpkg -i ruby-rspec-puppet_0.1.6-1_all.deb

#. Run unit tests for a Puppet module::

    cd fuel/deployment/puppet/module
    rake spec

Installing Cobbler
------------------

Install Cobbler from GitHub (it can't be installed from PyPi, and deb
package in Ubuntu is outdated)::

    cd ~
    git clone git://github.com/cobbler/cobbler.git
    cd cobbler
    git checkout release24
    sudo make install

Building Documentation
----------------------

You should prepare your build environment before you can build
this documentation. First you must install Java, using the
appropriate procedure for your operating system.

Java is needed to use PlantUML to automatically generate UML diagrams
from the source. You can also use `PlantUML Server
<http://www.plantuml.com/plantuml/>`_ for a quick preview of your
diagrams and language documentation.

Then you need to install all the packages required for creating of
the Python virtual environment and dependencies installation.
::

    sudo apt-get install make postgresql postgresql-server-dev-9.1
    sudo apt-get install python-dev python-pip python-virtualenv

Now you can create the virtual environment and activate it.
::

    virtualenv fuel-web-venv
    . virtualenv/bin/activate

And then install the dependencies.
::

    pip install -r nailgun/test-requirements.txt

Now you can look at the list of available formats and generate
the one you need:
::

    cd docs
    make help
    make html

There is a helper script **build-docs.sh**. It can perform
all the required steps automatically. The script can build documentation
in required format.
::

  Documentation build helper
  -o - Open generated documentation after build
  -c - Clear the build directory
  -n - Don't install any packages
  -f - Documentation format [html,signlehtml,latexpdf,pdf,epub]

For example, if you want to build HTML documentation you can just
use the following script, like this:
::

  ./build-docs.sh -f html -o

It will create virtualenv, install the required dependencies and
build the documentation in HTML format. It will also open the
documentation with your default browser.

If you don't want to install all the dependencies and you are not
interested in building automatic API documentation there is an easy
way to do it.

First remove autodoc modules from extensions section of **conf.py**
file in the **docs** directory. This section should be like this:
::

    extensions = [
        'rst2pdf.pdfbuilder',
        'sphinxcontrib.plantuml',
    ]

Then remove **develop/api_doc.rst** file and reference to it from
**develop.rst** index.

Now you can build documentation as usual using make command.
This method can be useful if you want to make some corrections to
text and see the results without building the entire environment.
The only Python packages you need are Sphinx packages:
::

    Sphinx
    sphinxcontrib-actdiag
    sphinxcontrib-blockdiag
    sphinxcontrib-nwdiag
    sphinxcontrib-plantuml
    sphinxcontrib-seqdiag

Just don't forget to rollback all these changes before you commit your
corrections.
