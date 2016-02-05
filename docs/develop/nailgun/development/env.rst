Setting up Environment
======================

For information on how to get source code see :ref:`getting-source`.

.. _nailgun_dependencies:

Preparing Development Environment
---------------------------------

.. warning:: Nailgun requires Python 2.7. Please check
    installed Python version using ``python --version``.

#. Nailgun can be found in fuel-web/nailgun

#. Install and configure PostgreSQL database. Please note that
   Ubuntu 12.04 requires postgresql-server-dev-9.1 while
   Ubuntu 14.04 requires postgresql-server-dev-9.3::

    sudo apt-get install --yes postgresql postgresql-server-dev-all

    sudo sed -ir 's/peer/trust/' /etc/postgresql/9.*/main/pg_hba.conf
    sudo service postgresql restart

    sudo -u postgres psql -c "CREATE ROLE nailgun WITH LOGIN PASSWORD 'nailgun'"
    sudo -u postgres createdb nailgun

   If required, you can specify Unix-domain
   socket in 'host' settings to connect to PostgreSQL database:

   .. code-block:: yaml

       DATABASE:
            engine: "postgresql"
            name: "nailgun"
            host: "/var/run/postgresql"
            port: ""
            user: "nailgun"
            passwd: "nailgun"

#. Install pip and development tools::

    sudo apt-get install --yes python-dev python-pip

#. Install virtualenv. This step increases flexibility
   when dealing with environment settings and package installation::

    sudo pip install virtualenv virtualenvwrapper
    . /usr/local/bin/virtualenvwrapper.sh  # you can save this to .bashrc
    mkvirtualenv fuel # you can use any name instead of 'fuel'
    workon fuel  # command selects the particular environment

#. Install Python dependencies. This section assumes that you use virtual environment.
   Otherwise, you must install all packages globally.
   You can install pip and use it to require all the other packages at once::

    sudo apt-get install --yes git
    git clone https://github.com/openstack/fuel-web.git
    cd fuel-web
    pip install --allow-all-external -r nailgun/test-requirements.txt

#. Install Nailgun in the developers mode by running the command below in the
   `nailgun` folder. Thanks to that, Nailgun extensions will be discovered::

    python setup.py develop

   Or if you are using pip::

    pip install -e .

#. Create required folder for log files::

    sudo mkdir /var/log/nailgun
    sudo chown -R `whoami`.`whoami` /var/log/nailgun
    sudo chmod -R a+w /var/log/nailgun

#. Install NodeJS and JS dependencies::

    sudo apt-get remove --yes nodejs nodejs-legacy
    sudo apt-get install --yes software-properties-common
    sudo add-apt-repository --yes ppa:chris-lea/node.js
    sudo apt-get update
    sudo apt-get install --yes nodejs
    sudo npm install -g gulp
    sudo chown -R `whoami`.`whoami` ~/.npm
    cd nailgun
    npm install

Setup for Nailgun Unit Tests
----------------------------

#. Nailgun unit tests use `Tox <http://testrun.org/tox/latest/>`_ for generating test
   environments. This means that you don't need to install all Python packages required
   for the project to run them, because Tox does this by itself.

#. First, create a virtualenv the way it's described in previous section. Then, install
   the Tox package::

    workon fuel #activate virtual environment created in the previous section
    pip install tox

#. Run the Nailgun backend unit tests and flake8 test::

    sudo apt-get install puppet-common #install missing package required by tasklib tests
    ./run_tests.sh

#. You can also run the same tests by hand, using tox itself::

    cd nailgun
    tox -epy26 -- -vv nailgun/test
    tox -epep8

#. Tox reuses the previously created environment. After making some changes with package
   dependencies, tox should be run with **-r** option to recreate existing virtualenvs::

    tox -r -epy26 -- -vv nailgun/test
    tox -r -epep8

Running Nailgun Performance Tests
+++++++++++++++++++++++++++++++++

Now you can run performance tests using -x option:

::

  ./run_tests.sh -x


If -x is not specified, run_tests.sh will not run performance tests.

The -n or -N option works exactly as before: it states whether
tests should be launched or not.

For example:

* run_tests.sh -n -x - run both regular and performance Nailgun tests.

* run_tests.sh -x - run nailgun performance tests only, do not run
  regular Nailgun tests.

* run_tests.sh -n - run regular Naigun tests only.

* run_tests.sh -N - run all tests except for Nailgun regular and
  performance tests.



Setup for Web UI Tests
----------------------

#. UI tests use Selenium server, so you need to install Java Runtime
   Environment (JRE) 1.6 or newer version.

#. You also need to install Firefox - it is used as the default browser for
   tests.

#. Run full Web UI test suite (this will wipe your Nailgun database in
   PostgreSQL)::

    cd nailgun
    npm run lint
    npm test

   By default Firefox browser is used. You can specify the browser using
   BROWSER environment variable::

    BROWSER=chrome npm test


.. _running-parallel-tests-py:

Running parallel tests with py.test
-----------------------------------

Now tests can be run over several processes
in a distributed manner; each test is executed
within an isolated database.

Prerequisites
+++++++++++++

- Nailgun user requires createdb permission.

- Postgres database is used for initial connection.

- If createdb cannot be granted for the environment,
  then several databases should be created. The number of
  databases should be equal to *TEST_WORKERS* variable.
  The *createdb* permission
  should have the following format: *nailgun0*, *nailgun1*.

- If no *TEST_WORKERS* variable is provided, then a default
  database name will be used. Often it is nailgun,
  but you can overwrite it with *TEST_NAILGUN_DB*
  environment variable.

- To execute parallel tests on your local environment,
  run the following command from *fuel-web/nailgun*:

  ::

       py.test -n 4 nailgun/test



  You can also run the it from *fuel-web*:

  ::


     py.test -n 4 nailgun/nailgun/test



.. _running-nailgun-in-fake-mode:

Running Nailgun in Fake Mode
----------------------------

#. Switch to virtual environment::

    workon fuel

#. Populate the database from fixtures::

    cd nailgun
    ./manage.py syncdb
    ./manage.py loaddefault # It loads all basic fixtures listed in settings.yaml
    ./manage.py loaddata nailgun/fixtures/sample_environment.json  # Loads fake nodes

#. Start application in "fake" mode, when no real calls to orchestrator
   are performed::

    python manage.py run -p 8000 --fake-tasks | egrep --line-buffered -v '^$|HTTP' >> /var/log/nailgun.log 2>&1 &

#. (optional) You can also use --fake-tasks-amqp option if you want to
   make fake environment use real RabbitMQ instead of fake one::

    python manage.py run -p 8000 --fake-tasks-amqp | egrep --line-buffered -v '^$|HTTP' >> /var/log/nailgun.log 2>&1 &

#. If you plan to use Fuel UI:

  * Update JS dependencies::

      npm install

  * If you don't plan to modify Fuel UI, you may want just to build static
    version which is served by nailgun::

      gulp build

    Please note that after pulling updates from fuel-web repo you may need to
    run this command again.

    To specify custom output directory location use
    `static-dir` option::

      gulp build --static-dir=static_compressed

    To speed up build process you may also want to disable uglification and
    source maps generation::

      gulp build --no-uglify --no-sourcemaps

  * If you plan to modify Fuel UI, there is more convenient option --
    a development server. It watches for file changes and automatically
    rebuilds changed modules (significantly faster than full rebuild)
    and triggers page refresh in browsers::

      gulp dev-server

    By default it runs on port 8080 and assumes that nailgun runs on
    port 8000. You can override this by using the following options::

      gulp dev-server --dev-server-host=127.0.0.1 --dev-server-port=8080 --nailgun-host=127.0.0.1 --nailgun-port=8000

    If you don't want to use a development server but would like to recompile
    the bundle on any change, use::

      gulp build --watch

    If automatic rebuild on change doesn't work, most likely you need to
    increase the limit of inotify watches::

      echo 100000 | sudo tee /proc/sys/fs/inotify/max_user_watches


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


Flushing database before/after running tests
--------------------------------------------

The database should be cleaned after running tests;
before parallel tests were enabled,
you could only run dropdb with *./run_tests.sh* script.

Now you need to run dropdb for each slave node:
the *py.test --cleandb <path to the tests>* command is introduced for this
purpose.
