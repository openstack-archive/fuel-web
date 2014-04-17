Fuel Development Environment
============================

Basic OS for Fuel development is Ubuntu Linux. Setup instructions below
assume Ubuntu 13.04, most of them should be applicable to other Ubuntu
and Debian versions, too.

Each subsequent section below assumes that you have followed the steps
described in all preceding sections. By the end of this document, you
should be able to run and test all key components of Fuel, build Fuel
master node installation ISO, and generate documentation.

.. _getting-source:

Getting the Source Code
-----------------------

Source code of OpenStack Fuel can be found on Stackforge::

    git clone https://github.com/stackforge/fuel-main
    git clone https://github.com/stackforge/fuel-web
    git clone https://github.com/stackforge/fuel-astute
    git clone https://github.com/stackforge/fuel-ostf
    git clone https://github.com/stackforge/fuel-library
    git clone https://github.com/stackforge/fuel-docs


Nailgun (Fuel-Web)
------------------
See :ref:`nailgun-development`


Astute
----------------

#. Astute can be found in fuel-astute repository

#. Install Ruby dependencies::

    sudo apt-get install git curl
    \curl -L https://get.rvm.io | bash -s stable
    rvm install 1.9.3

#. Install or update dependencies and run unit tests::

    cd fuel-astute
    ./run_tests.sh

#. (optional) Run Astute MCollective integration test (you'll need to
   have MCollective server running for this to work)::

    cd fuel-astute
    bundle exec rspec spec/integration/mcollective_spec.rb

.. _building-fuel-iso:

Building the Fuel ISO
---------------------

#. Following software is required to build the Fuel ISO images on Ubuntu
   12.10 or newer::

    sudo apt-get remove nodejs nodejs-legacy
    sudo apt-get install software-properties-common
    sudo add-apt-repository ppa:chris-lea/node.js
    sudo apt-get update
    sudo apt-get install build-essential make git ruby ruby-dev rubygems debootstrap
    sudo apt-get install python-setuptools yum yum-utils libmysqlclient-dev isomd5sum
    sudo apt-get install python-nose libvirt-bin python-ipaddr python-paramiko python-yaml
    sudo apt-get install python-pip kpartx extlinux unzip genisoimage nodejs
    sudo gem install bundler -v 1.2.1
    sudo gem install builder
    sudo pip install xmlbuilder jinja2
    sudo npm install -g grunt-cli

#. (alternative) If you have completed the instructions in the previous
   sections of Fuel development environment setup guide, the list of
   additional packages required to build the ISO becomes shorter::

    sudo apt-get install ruby-dev ruby-builder bundler libmysqlclient-dev
    sudo apt-get install yum-utils kpartx extlinux genisoimage isomd5sum

#. ISO build process requires sudo permissions, allow yourself to run
   commands as root user without request for a password::

    echo "`whoami` ALL=(ALL) NOPASSWD: ALL" | sudo tee -a /etc/sudoers

#. If you haven't already done so, get the source code::

    git clone https://github.com/stackforge/fuel-main

#. Now you can build the Fuel ISO image::

    cd fuel-main
    make iso

#. To build an ISO image from custom branches of fuel, astute, nailgun
   or ostf-tests, edit the "Repos and versions" section of config.mk.

#. To build an ISO image from custom gerrit patches on review, edit the
   "Gerrit URLs and commits" section of config.mk, e.g. for
   https://review.openstack.org/#/c/63732/8 (id:63732, patch:8) set
   FUELLIB_GERRIT_COMMIT?=refs/changes/32/63732/8

Running Fuel Puppet Modules Unit Tests
--------------------------------------

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

    pip install ./shotgun
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
use this thispt like this:
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
