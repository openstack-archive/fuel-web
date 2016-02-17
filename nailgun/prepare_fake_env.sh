#!/bin/bash

# Configure directories where to prepare 'fake' environment
FUEL_WEB=/tmp/fuel-web
FUEL_WEB_ENV=fuel-web-env

echo "Installing package dependencies..."
sudo apt-get install -y \
    git \
    libjpeg-dev \
    libyaml-dev \
    nodejs \
    nodejs-legacy \
    npm \
    postgresql \
    postgresql-server-dev-all \
    python-dev \
    python-pip \
    python-virtualenv

echo "Configuring database..."
sudo sed -ir "s/peer/trust/" /etc/postgresql/9.*/main/pg_hba.conf
sudo service postgresql restart

sudo -u postgres psql -c "CREATE ROLE nailgun WITH LOGIN PASSWORD 'nailgun'"
sudo -u postgres createdb nailgun

git clone https://github.com/openstack/fuel-web.git "${FUEL_WEB}"

echo "Creating virtual environment..."
cd ${FUEL_WEB}
virtualenv -p python2.7 "${FUEL_WEB_ENV}"
echo "Activating ${FUEL_WEB_ENV}..."
source "${FUEL_WEB_ENV}/bin/activate"

# Install python packages from test-requirements.txt
pip install --allow-all-external -r nailgun/test-requirements.txt

cd "${FUEL_WEB}/nailgun"
./manage.py syncdb
./manage.py loaddefault # It loads all basic fixtures listed in settings.yaml
./manage.py loaddata nailgun/fixtures/sample_environment.json  # Loads fake nodes

echo "Creating required folder for log files..."
sudo mkdir /var/log/nailgun
sudo chown -R `whoami`.`whoami` /var/log/nailgun
sudo chmod -R a+w /var/log/nailgun

echo "Installing gulp..."
npm install gulp
sudo chown -R `whoami`.`whoami` ~/.npm
cd "${FUEL_WEB}/nailgun"

echo "Installing npm..."
npm install
cd "${FUEL_WEB}/nailgun"
"${FUEL_WEB}"/nailgun/node_modules/.bin/gulp build --static-dir=static_compressed

echo "======================================="
echo "...READY to run nailgun in fake mode..."
echo "Please, activate virtualenv:"
echo "     source ${FUEL_WEB}/${FUEL_WEB_ENV}/bin/activate"
echo "Change your directory: "
echo "     cd ${FUEL_WEB}/nailgun"
echo "Run nailgun in fake mode: "
echo "     python manage.py run -p 8000 --fake-tasks | egrep --line-buffered -v '^$|HTTP' >> /var/log/nailgun/nailgun.log 2>&1 &"