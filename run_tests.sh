#!/bin/bash

#    Copyright 2013 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

set -eu

function usage {
  echo "Usage: $0 [OPTION]..."
  echo "Run Fuel-Web test suite(s)"
  echo ""
  echo "  -a, --agent                 Run FUEL_AGENT unit tests"
  echo "  -A, --no-agent              Don't run FUEL_AGENT unit tests"
  echo "  -n, --nailgun               Run NAILGUN both unit and integration tests"
  echo "  -N, --no-nailgun            Don't run NAILGUN tests"
  echo "  -w, --webui                 Run WEB-UI tests"
  echo "  -W, --no-webui              Don't run WEB-UI tests"
  echo "  -c, --cli                   Run FUELCLIENT tests"
  echo "  -C, --no-cli                Don't run FUELCLIENT tests"
  echo "  -u, --upgrade               Run tests for UPGRADE system"
  echo "  -U, --no-upgrade            Don't run tests for UPGRADE system"
  echo "  -s, --shotgun               Run SHOTGUN tests"
  echo "  -S, --no-shotgun            Don't run SHOTGUN tests"
  echo "  -p, --flake8                Run FLAKE8 and HACKING compliance check"
  echo "  -P, --no-flake8             Don't run static code checks"
  echo "  -j, --jslint                Run JSLINT compliance checks"
  echo "  -J, --no-jslint             Don't run JSLINT checks"
  echo "  -t, --tests                 Run a given test files"
  echo "  -h, --help                  Print this usage message"
  echo ""
  echo "Note: with no options specified, the script will try to run all available"
  echo "      tests with all available checks."
  exit
}


function process_options {
  for arg in $@; do
    case "$arg" in
      -h|--help) usage;;
      -a|--agent) agent_tests=1;;
      -A|--no-agent) no_agent_tests=1;;
      -n|--nailgun) nailgun_tests=1;;
      -N|--no-nailgun) no_nailgun_tests=1;;
      -w|--webui) webui_tests=1;;
      -W|--no-webui) no_webui_tests=1;;
      -c|--cli) cli_tests=1;;
      -C|--no-cli) no_cli_tests=1;;
      -u|--upgrade) upgrade_system=1;;
      -U|--no-upgrade) no_upgrade_system=1;;
      -s|--shotgun) shotgun_tests=1;;
      -S|--no-shotgun) no_shotgun_tests=1;;
      -p|--flake8) flake8_checks=1;;
      -P|--no-flake8) no_flake8_checks=1;;
      -j|--jslint) jslint_checks=1;;
      -J|--no-jslint) no_jslint_checks=1;;
      -t|--tests) certain_tests=1;;
      -*) testropts="$testropts $arg";;
      *) testrargs="$testrargs $arg"
    esac
  done
}

# settings
ROOT=$(dirname `readlink -f $0`)
TESTRTESTS="nosetests"
FLAKE8="flake8"
PEP8="pep8"
CASPERJS="casperjs"
JSLINT="grunt jslint"

# test options
testrargs=
testropts="--with-timer --timer-warning=10 --timer-ok=2 --timer-top-n=10"

# nosetest xunit options
NAILGUN_XUNIT=${NAILGUN_XUNIT:-"$ROOT/nailgun.xml"}
FUELCLIENT_XUNIT=${FUELCLIENT_XUNIT:-"$ROOT/fuelclient.xml"}
FUELUPGRADE_XUNIT=${FUELUPGRADE_XUNIT:-"$ROOT/fuelupgrade.xml"}
FUELUPGRADEDOWNLOADER_XUNIT=${FUELUPGRADEDOWNLOADER_XUNIT:-"$ROOT/fuelupgradedownloader.xml"}
SHOTGUN_XUNIT=${SHOTGUN_XUNIT:-"$ROOT/shotgun.xml"}
UI_SERVER_PORT=${UI_SERVER_PORT:-5544}
FUELCLIENT_SERVER_PORT=${FUELCLIENT_SERVER_PORT:-8003}
TEST_NAILGUN_DB=${TEST_NAILGUN_DB:-nailgun}
ARTIFACTS=${ARTIFACTS:-`pwd`/test_run}
mkdir -p $ARTIFACTS

# disabled/enabled flags that are setted from the cli.
# used for manipulating run logic.
agent_tests=0
no_agent_tests=0
nailgun_tests=0
no_nailgun_tests=0
webui_tests=0
no_webui_tests=0
cli_tests=0
no_cli_tests=0
upgrade_system=0
no_upgrade_system=0
shotgun_tests=0
no_shotgun_tests=0
flake8_checks=0
no_flake8_checks=0
jslint_checks=0
no_jslint_checks=0
certain_tests=0


function run_tests {
  run_cleanup
  # This variable collects all failed tests. It'll be printed in
  # the end of this function as a small statistic for user.
  local errors=""
  # If tests was specified in command line then run only these tests
  if [ $certain_tests -eq 1 ]; then
    for testfile in $testrargs; do
      local testfile=`readlink -f $testfile`
      guess_test_run $testfile
    done
    exit
  fi

  # Enable all tests if none was specified skipping all explicitly disabled tests.
  if [[ $agent_tests -eq 0 && \
      $nailgun_tests -eq 0 && \
      $webui_tests -eq 0 && \
      $cli_tests -eq 0 && \
      $upgrade_system -eq 0 && \
      $shotgun_tests -eq 0 && \
      $flake8_checks -eq 0 && \
      $jslint_checks -eq 0 ]]; then

    if [ $no_agent_tests -ne 1 ];  then agent_tests=1;  fi
    if [ $no_nailgun_tests -ne 1 ];  then nailgun_tests=1;  fi
    if [ $no_webui_tests -ne 1 ];    then webui_tests=1;    fi
    if [ $no_cli_tests -ne 1 ];      then cli_tests=1;      fi
    if [ $no_upgrade_system -ne 1 ]; then upgrade_system=1; fi
    if [ $no_shotgun_tests -ne 1 ];  then shotgun_tests=1;  fi
    if [ $no_flake8_checks -ne 1 ];  then flake8_checks=1;  fi
    if [ $no_jslint_checks -ne 1 ];  then jslint_checks=1;  fi
  fi

  # Run all enabled tests
  if [ $flake8_checks -eq 1 ]; then
    echo "Starting Flake8 tests..."
    run_flake8 || errors+=" flake8_checks"
  fi

  if [ $agent_tests -eq 1 ]; then
    echo "Starting Agent tests..."
    run_agent_tests || errors+=" agent_tests"
  fi

  if [ $nailgun_tests -eq 1 ]; then
    echo "Starting Nailgun tests..."
    run_nailgun_tests || errors+=" nailgun_tests"
  fi

  if [ $webui_tests -eq 1 ]; then
    echo "Starting WebUI tests..."
    run_webui_tests || errors+=" webui_tests"
  fi

  if [ $cli_tests -eq 1 ]; then
    echo "Starting Fuel client tests..."
    run_cli_tests || errors+=" cli_tests"
  fi

  if [ $upgrade_system -eq 1 ]; then
    echo "Starting upgrade system tests..."
    run_upgrade_system_tests || errors+=" upgrade_system_tests"
  fi

  if [ $shotgun_tests -eq 1 ]; then
    echo "Starting Shotgun tests..."
    run_shotgun_tests || errors+=" shotgun_tests"
  fi

  if [ $jslint_checks -eq 1 ]; then
    echo "Starting JSLint tests..."
    run_jslint || errors+=" jslint_checks"
  fi

  # print failed tests
  if [ -n "$errors" ]; then
    echo Failed tests: $errors
    exit 1
  fi

  exit
}

# Run agent tests
#
# Arguments:
#
#   $@ -- tests to be run; with no arguments all tests will be run
function run_agent_tests {
  local result=0

  pushd $ROOT/fuel_agent >> /dev/null

  # run tests
  tox -epy26 || result=1

  popd >> /dev/null

  return $result
}

# Run both integration and unit Nailgun's tests.
#
# Arguments:
#
#   $@ -- tests to be run; with no arguments all tests will be run
#
# It is supposed that we prepare database (run DBMS and create schema)
# before running tests.
function run_nailgun_tests {
  local TESTS="$ROOT/nailgun/nailgun/test"
  local result=0
  local artifacts=$ARTIFACTS/nailgun
  local config=$artifacts/test.yaml
  prepare_artifacts $artifacts $config
  if [ $# -ne 0 ]; then
    TESTS="$@"
  fi

  # prepare database
  dropdb $config
  syncdb $config false

  pushd $ROOT/nailgun >> /dev/null
  # # run tests
  NAILGUN_CONFIG=$config \
  tox -epy26 -- -vv $testropts $TESTS --xunit-file $NAILGUN_XUNIT || result=1
  popd >> /dev/null
  return $result
}

# Run webui tests.
#
# Arguments:
#
#   $@ -- tests to be run; with no arguments all tests will be run
function run_webui_tests {
  local SERVER_PORT=$UI_SERVER_PORT
  local TESTS_DIR=$ROOT/nailgun/ui_tests
  local TESTS=$TESTS_DIR/test_*.js
  local artifacts=$ARTIFACTS/webui
  local config=$artifacts/test.yaml
  prepare_artifacts $artifacts $config
  local COMPRESSED_STATIC_DIR=$artifacts/static_compressed

  if [ $# -ne 0 ]; then
    TESTS=$@
  fi

  pushd $ROOT/nailgun >> /dev/null

  # test compression
  echo -n "Compressing UI... "
  local output=$(grunt build --static-dir=$COMPRESSED_STATIC_DIR 2>&1)
  if [ $? -ne 0 ]; then
    echo "$output"
    popd >> /dev/null
    exit 1
  fi
  echo "done"

  # run js testcases
  local server_log=`mktemp /tmp/test_nailgun_ui_server.XXXX`
  local result=0

  for testcase in $TESTS; do

    dropdb $config
    syncdb $config true

    local pid=`run_server $SERVER_PORT $server_log $config`

    if [ $pid -ne 0 ]; then
      SERVER_PORT=$SERVER_PORT \
      ${CASPERJS} test --includes="$TESTS_DIR/helpers.js" --fail-fast "$testcase"
      if [ $? -ne 0 ]; then
        result=1
        break
      fi

      kill $pid
      wait $pid 2> /dev/null
    else
      cat $server_log
      result=1
      break
    fi

  done

  rm $server_log
  popd >> /dev/null

  return $result
}


# Run fuelclient tests.
#
# Arguments:
#
#   $@ -- tests to be run; with no arguments all tests will be run
#
# It is supposed that nailgun server is up and working.
# We are going to pass nailgun url to test runner.
function run_cli_tests {
  local SERVER_PORT=$FUELCLIENT_SERVER_PORT
  local TESTS=$ROOT/fuelclient/tests
  local artifacts=$ARTIFACTS/cli
  local config=$artifacts/test.yaml
  prepare_artifacts $artifacts $config

  if [ $# -ne 0 ]; then
    TESTS=$@
  fi

  local server_log=`mktemp /tmp/test_nailgun_cli_server.XXXX`
  local result=0

  dropdb $config
  syncdb $config true

  local pid=`run_server $SERVER_PORT $server_log $config`

  if [ $pid -ne 0 ]; then

    pushd $ROOT/fuelclient >> /dev/null
    # run tests
    NAILGUN_CONFIG=$config LISTEN_PORT=$SERVER_PORT \
    tox -epy26 -- -vv $testropts $TESTS --xunit-file $FUELCLIENT_XUNIT || result=1
    popd >> /dev/null

    kill $pid
    wait $pid 2> /dev/null
  else
    cat $server_log
    result=1
  fi

  rm $server_log

  return $result
}

# Run tests for fuel upgrade system
#
# Arguments:
#
#   $@ -- tests to be run; with no arguments all tests will be run
function run_upgrade_system_tests {
  local UPGRADE_TESTS="$ROOT/fuel_upgrade_system/fuel_upgrade/fuel_upgrade/tests/"
  local DOWNLOADER_TESTS="$ROOT/fuel_upgrade_system/fuel_update_downloader/fuel_update_downloader/tests/"

  local result=0

  if [ $# -ne 0 ]; then
    # run selected tests
    TESTS="$@"
    $TESTRTESTS -vv $testropts $TESTS || result=1
  else
    # run all tests
    pushd $ROOT/fuel_upgrade_system/fuel_upgrade >> /dev/null
    tox -epy26 -- -vv $testropts $UPGRADE_TESTS --xunit-file $FUELUPGRADE_XUNIT || result=1
    popd >> /dev/null

    pushd $ROOT/fuel_upgrade_system/fuel_update_downloader >> /dev/null
    tox -epy26 -- -vv $testropts $DOWNLOADER_TESTS --xunit-file $FUELUPGRADEDOWNLOADER_XUNIT || result=1
    popd >> /dev/null

  fi

  return $result
}


# Run shotgun tests
#
# Arguments:
#
#   $@ -- tests to be run; with no arguments all tests will be run
function run_shotgun_tests {
  local result=0

  pushd $ROOT/shotgun >> /dev/null

  # run tests
  tox -epy26 || result=1

  popd >> /dev/null

  return $result
}

function run_flake8_subproject {
  local DIRECTORY=$1
  local result=0
  pushd $ROOT/$DIRECTORY >> /dev/null
  tox -epep8 || result=1
  popd >> /dev/null
  return $result
}

# Check python code with flake8 and pep8.
#
# Some settings description:
#
# * __init__.py --- excluded because it doesn't comply with pep8 standard
# * H302 --- "import only modules. does not import a module" requires to import
#            only modules and not functions
# * H802 --- first line of git commit commentary should be less than 50 characters
function run_flake8 {
  local result=0
  run_flake8_subproject fuel_agent && \
  run_flake8_subproject nailgun && \
  run_flake8_subproject fuelclient && \
  run_flake8_subproject fuelmenu && \
  run_flake8_subproject network_checker && \
  run_flake8_subproject fuel_upgrade_system/fuel_update_downloader && \
  run_flake8_subproject fuel_upgrade_system/fuel_upgrade && \
  run_flake8_subproject fuel_development && \
  run_flake8_subproject shotgun || result=1
  return $result
}


# Check javascript files with `jslint`. It's necessary to run it inside
# `nailgun` folder, so we temporary change current dir.
function run_jslint {
  pushd $ROOT/nailgun >> /dev/null

  local result=0
  ${JSLINT} || result=1

  popd >> /dev/null
  return $result
}


# Remove temporary files. No need to run manually, since it's
# called automatically in `run_tests` function.
function run_cleanup {
  find . -type f -name "*.pyc" -delete
  rm -f *.log
  rm -f *.pid
}


# Arguments:
#
#   $1 -- insert default data into database if true
function syncdb {
  pushd $ROOT/nailgun >> /dev/null
  local config=$1
  local defaults=$2
  NAILGUN_CONFIG=$config tox -evenv -- python manage.py syncdb > /dev/null

  if [[ $# -ne 0 && $defaults = true ]]; then
    NAILGUN_CONFIG=$config tox -evenv -- python manage.py loaddefault > /dev/null
  fi

  popd >> /dev/null
}


function dropdb {
  pushd $ROOT/nailgun >> /dev/null
  local config=$1
  NAILGUN_CONFIG=$config tox -evenv -- python manage.py dropdb > /dev/null

  popd >> /dev/null
}


# Arguments:
#
#   $1 -- server port
#   $2 -- path to log file
#   $3 -- path to the server config
#
# Returns: a server pid, that you have to close manually
function run_server {
  local SERVER_PORT=$1
  local SERVER_LOG=$2
  local SERVER_SETTINGS=$3

  local RUN_SERVER="\
    python manage.py run \
      --port=$SERVER_PORT \
      --config=$SERVER_SETTINGS \
      --fake-tasks \
      --fake-tasks-tick-count=80 \
      --fake-tasks-tick-interval=1"

  pushd $ROOT/nailgun >> /dev/null

  # kill old server instance if exists
  local pid=`lsof -ti tcp:$SERVER_PORT`
  if [ -n "$pid" ]; then
    kill $pid
    sleep 5
  fi

  # run new server instance
  tox -evenv -- $RUN_SERVER >> $SERVER_LOG 2>&1 &

  # wait for server availability
  which nc > /dev/null
  if [ $? -eq 0 ]; then
    for i in {1..50}; do
      local http_code=`curl -s -w %{http_code} -o /dev/null -I http://0.0.0.0:$SERVER_PORT/`
      if [ http_code = 200 ]; then break; fi
      sleep 0.1
    done
  else
    sleep 5
  fi
  popd >> /dev/null
  echo `lsof -ti tcp:$SERVER_PORT`
}

function prepare_artifacts {
  local artifacts=$1
  local config=$2
  mkdir -p $artifacts
  create_settings_yaml $config $artifacts
}

function create_settings_yaml {
  local config_path=$1
  local artifacts_path=$2
  cat > $config_path <<EOL
DEVELOPMENT: 1
STATIC_DIR: ${artifacts_path}/static_compressed
TEMPLATE_DIR: ${artifacts_path}/static_compressed
DATABASE:
  name: ${TEST_NAILGUN_DB}
  engine: "postgresql"
  host: "localhost"
  port: "5432"
  user: "nailgun"
  passwd: "nailgun"
API_LOG: ${artifacts_path}/api.log
APP_LOG: ${artifacts_path}/app.log
EOL
}

# Detect test runner for a given testfile and then run the test with
# this runner.
#
# Arguments:
#
#   $1 -- path to the test file
function guess_test_run {
  if [[ $1 == *ui_tests* && $1 == *.js ]]; then
    run_webui_tests $1 || echo "ERROR: $1"
  elif [[ $1 == *fuelclient* ]]; then
    run_cli_tests $1 || echo "ERROR: $1"
  elif [[ $1 == *fuel_upgrade_system* ]]; then
    run_upgrade_system_tests $1 || echo "ERROR: $1"
  elif [[ $1 == *shotgun* ]]; then
    run_shotgun_tests $1 || echo "ERROR: $1"
  else
    run_nailgun_tests $1 || echo "ERROR: $1"
  fi
}


# parse command line arguments and run the tests
process_options $@
run_tests
