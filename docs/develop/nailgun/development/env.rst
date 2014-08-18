Setting up Environment
======================

For information on how to get source code see :ref:`getting-source`.

.. _nailgun_dependencies:

Preparing Development Environment
---------------------------------

.. warning:: Nailgun requires Python 2.6. Please check installed Python version
    using ``python --version``. If the version check does not match, you can use
    `PPA <https://launchpad.net/~fkrull/+archive/ubuntu/deadsnakes>`_ (Ubuntu)
    or  `pyenv <https://github.com/yyuu/pyenv>`_ (Universal)

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


Setup for Nailgun Unit Tests
----------------------------

#. Nailgun unit tests use `Tox <http://testrun.org/tox/latest/>`_ for generating test
   environments. This means that you don't need to install all Python packages required
   for the project to run them, because Tox does this by itself.

#. First, create a virtualenv the way it's described in previous section. Then, install
   the Tox package::

    pip install tox

#. Run the Nailgun backend unit tests::

    ./run_tests.sh --no-jslint --no-webui

#. Run the Nailgun flake8 test::

    ./run_tests.sh --flake8

#. You can also run the same tests by hand, using tox itself::

    cd nailgun
    tox -epy26 -- -vv nailgun/test
    tox -epep8

#. Tox reuses the previously created environment. After making some changes with package
   dependencies, tox should be run with **-r** option to recreate existing virtualenvs::

    tox -r -epy26 -- -vv nailgun/test
    tox -r -epep8


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

.. _running-nailgun-in-fake-mode:

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

Note: Diagnostic Snapshot is not available in a Fake mode.

Running the Fuel System Tests
-----------------------------

For fuel-devops configuration info please refer to
:doc:`Devops Guide </devops>` article.

#. Run the integration test::

    cd fuel-main
    make test-integration

#. To save time, you can execute individual test cases from the
   integration test suite like this (nice thing about TestAdminNode
   is that it takes you from nothing to a Fuel master with 9 blank nodes
   connected to 3 virtual networks)::

    cd fuel-main
    export PYTHONPATH=$(pwd)
    export ENV_NAME=fuelweb
    export PUBLIC_FORWARD=nat
    export ISO_PATH=`pwd`/build/iso/fuelweb-centos-6.5-x86_64.iso
    ./fuelweb_tests/run_tests.py --group=test_cobbler_alive

#. The test harness creates a snapshot of all nodes called 'empty'
   before starting the tests, and creates a new snapshot if a test
   fails. You can revert to a specific snapshot with this command::

    dos.py revert --snapshot-name <snapshot_name> <env_name>

#. To fully reset your test environment, tell the Devops toolkit to erase it::

    dos.py list
    dos.py erase <env_name>

