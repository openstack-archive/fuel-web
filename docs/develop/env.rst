Fuel Development Environment
============================

Basic OS for Fuel development is Ubuntu Linux. Setup instructions below
assume Ubuntu 13.04, most of them should be applicable to other Ubuntu
and Debian versions, too.

Each subsequent section below assumes that you have followed the steps
described in all preceding sections. By the end of this document, you
should be able to run and test all key components of Fuel, build Fuel
master node installation ISO, and generate documentation.

Getting the Source Code
-----------------------

Source code of OpenStack Fuel can be found on Stackforge::

    git clone https://github.com/stackforge/fuel-main
    git clone https://github.com/stackforge/fuel-web
    git clone https://github.com/stackforge/fuel-astute
    git clone https://github.com/stackforge/fuel-ostf
    git clone https://github.com/stackforge/fuel-library
    git clone https://github.com/stackforge/fuel-docs

.. _nailgun_dependencies:

Setup for Nailgun Unit Tests
----------------------------

#. Nailgun can be found in fuel-web/nailgun

#. Install and configure PostgreSQL database::

    sudo apt-get install postgresql postgresql-server-dev-9.1
    sudo -u postgres createuser -SDRP nailgun  # enter password "nailgun"
    sudo -u postgres createdb nailgun

#. Install pip and development tools::

    sudo apt-get install python-dev python-pip

#. Install virtualenv. That is optional step that increases flexibility
   when dealing with environment settings and package installation::

    sudo pip install virtualenv virtualenvwrapper
    source /usr/local/bin/virtualenvwrapper.sh  # you can save this to .bashrc
    mkvirtualenv fuel  # you can use any name instead of 'fuel'
    workon fuel  # command selects the particular environment

#. Install Python dependencies. This section assumes that you use virtual environment.
   Otherwise, you have to install all this stuff globally.
   There is a file called "setup.py" which can be used to install all Python dependencies,
   so you can install pip and then all of them at once::

    pip install ./shotgun  # this fuel project is listed in setup.py requirements
    cd nailgun
    pip install -r test-requirements.txt
    cd ..

#. Create required folder for log files::

    sudo mkdir /var/log/nailgun
    sudo chown -R `whoami`.`whoami` /var/log/nailgun

#. Run the Nailgun backend unit tests::

    ./run_tests.sh --no-jslint --no-ui-tests

#. Run the Nailgun flake8 test::

    ./run_tests.sh --flake8

Setup for Web UI Tests
----------------------

#. Install NodeJS and JS dependencies::

    sudo apt-get remove nodejs nodejs-legacy
    sudo apt-get install software-properties-common
    sudo add-apt-repository ppa:chris-lea/node.js
    sudo apt-get update
    sudo apt-get install nodejs
    sudo npm install -g grunt-cli
    cd nailgun
    npm install

#. Install CasperJS::

    sudo npm install -g phantomjs
    cd ~
    git clone git://github.com/n1k0/casperjs.git
    cd casperjs
    git checkout tags/1.0.0-RC4
    sudo ln -sf `pwd`/bin/casperjs /usr/local/bin/casperjs

#. Run full Web UI test suite (this will wipe your Nailgun database in
   PostgreSQL)::

    cd fuel-web
    ./run_tests.sh --jslint
    ./run_tests.sh --ui-tests

Running Nailgun in Fake Mode
----------------------------

#. Fetch JS dependencies::

    cd nailgun
    npm install
    grunt bower

#. Populate the database from fixtures::

    ./manage.py syncdb
    ./manage.py loaddefault # It loads all basic fixtures listed in settings.yaml
    ./manage.py loaddata nailgun/fixtures/sample_environment.json  # Loads fake nodes

#. Start application in "fake" mode, when no real calls to orchestrator
   are performed::

    python manage.py run -p 8000 --fake-tasks | egrep --line-buffered -v '^$|HTTP' >> /var/log/nailgun.log 2>&1 &

#. (optional) You can also use --fake-tasks-amqp option if you want to
   make fake environment use real RabbitMQ instead of fake one::

    python manage.py run -p 8000 --fake-tasks-amqp | egrep --line-buffered -v '^$|HTTP' >> /var/log/nailgun.log 2>&1 &

#. (optional) To create a compressed version of UI and put it into static_compressed dir::

    grunt build --static-dir=static_compressed

Astute and Naily
----------------

#. Astute and Naily can be found in fuel-astute repository

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

Running the FuelWeb Integration Test
------------------------------------

#. Install libvirt and Devops library dependencies::

    sudo apt-get install libvirt-bin python-libvirt python-ipaddr python-paramiko
    sudo pip install xmlbuilder django==1.4.3

#. Configure permissions for libvirt and relogin or restart your X for
   the group changes to take effect (consult /etc/libvirt/libvirtd.conf
   for the group name)::

    GROUP=`grep unix_sock_group /etc/libvirt/libvirtd.conf|cut -d'"' -f2`
    sudo useradd `whoami` kvm
    sudo useradd `whoami` $GROUP
    chgrp $GROUP /var/lib/libvirt/images
    chmod g+w /var/lib/libvirt/images

#. Clone the Mirantis Devops virtual environment manipulation library
   from GitHub and install it where FuelWeb Integration Test can find
   it::

    git clone git@github.com:Mirantis/devops.git
    cd devops
    python setup.py build
    sudo python setup.py install

#. Configure and populate the Devops DB::

    SETTINGS=/usr/local/lib/python2.7/dist-packages/devops-2.0-py2.7.egg/devops/settings.py
    sed -i "s/'postgres'/'devops'/" $SETTINGS
    echo "SECRET_KEY = 'secret'" >> $SETTINGS
    sudo -u postgres createdb devops
    sudo -u postgres createuser -SDR devops
    django-admin.py syncdb --settings=devops.settings

#. Run the integration test::

    cd fuel-main
    make test-integration

#. To save time, you can execute individual test cases from the
   integration test suite like this (nice thing about TestAdminNode
   is that it takes you from nothing to a Fuel master with 9 blank nodes
   connected to 3 virtual networks)::

    cd fuel-main
    export ENV_NAME=fuelweb
    export PUBLIC_FORWARD=nat
    export ISO_PATH=`pwd`/build/iso/fuelweb-centos-6.4-x86_64.iso
    nosetests -w fuelweb_test -s fuelweb_test.integration.test_admin_node:TestAdminNode.test_cobbler_alive

#. The test harness creates a snapshot of all nodes called 'empty'
   before starting the tests, and creates a new snapshot if a test
   fails. You can revert to a specific snapshot with this command::

    dos.py revert --snapshot-name <snapshot_name> <env_name>

#. To fully reset your test environment, tell the Devops toolkit to erase it::

    dos.py list
    dos.py erase <env_name>

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

#. Before you can build this documentation you should prepare your
building environment first. The first thing you need to do is to
install Java. There are a lot of ways to do it depending on your
operating system.

Java is needed to use PlantUML to automatically generate UML diagrams
from the source. You can also use `PlantUML Server
<http://www.plantuml.com/plantuml/>`_ for a quick preview of your
diagrams and language documentation.

#. You will need to follow steps from :ref:`nailgun_dependencies`
section to build documentation. All these dependencies are needed
for automatic API documentation generation. If you are not going to
run unit tests there is no need to actually setup PostgreSQL server.
Only dev packages are needed to install all required Python dependencies.

#. Look at the list of available formats and generate the one you need::

    cd docs
    make help
    make html

#. There is also a special script **build-docs.sh**. It will perform
all required steps automatically except Java installation. The script
will build documentation in required format.
::

  Documentation build helper
  -o - Open generated documentation after build
  -f - Documentation format [html,signlehtml,pdf,ebub]

#. If you don't want to install all the dependencies and you are not
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