Setting up Environment
======================

For information on how to get source code see :ref:`getting-source`.

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

#. Install virtualenv. This is an optional step that increases flexibility
   when dealing with environment settings and package installation::

    sudo pip install virtualenv virtualenvwrapper
    source /usr/local/bin/virtualenvwrapper.sh  # you can save this to .bashrc
    mkvirtualenv fuel  # you can use any name instead of 'fuel'
    workon fuel  # command selects the particular environment

#. Install Python dependencies. This section assumes that you use virtual environment.
   Otherwise, you must install all packages globally.
   You can install pip and use it to require all the other packages at once.::

    pip install ./shotgun  # this fuel project is listed in setup.py requirements
    pip install --allow-all-external -r nailgun/test-requirements.txt

#. Create required folder for log files::

    sudo mkdir /var/log/nailgun
    sudo chown -R `whoami`.`whoami` /var/log/nailgun

#. Run the Nailgun backend unit tests::

    ./run_tests.sh --no-jslint --no-webui

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
    ./run_tests.sh --webui


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
    export ISO_PATH=`pwd`/build/iso/fuelweb-centos-6.5-x86_64.iso
    nosetests -w fuelweb_test -s fuelweb_test.integration.test_admin_node:TestAdminNode.test_cobbler_alive

#. The test harness creates a snapshot of all nodes called 'empty'
   before starting the tests, and creates a new snapshot if a test
   fails. You can revert to a specific snapshot with this command::

    dos.py revert --snapshot-name <snapshot_name> <env_name>

#. To fully reset your test environment, tell the Devops toolkit to erase it::

    dos.py list
    dos.py erase <env_name>
