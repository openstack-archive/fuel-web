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
  echo "  -h, --help                  Print this usage message"
  echo "  -k, --tasklib               Run tasklib unit and functional tests"
  echo "  -K, --no-tasklib            Don't run tasklib unit and functional tests"
  echo "  -l, --lint-ui               Run UI linting tasks"
  echo "  -L, --no-lint-ui            Don't run UI linting tasks"
  echo "  -n, --nailgun               Run NAILGUN unit/integration tests"
  echo "  -N, --no-nailgun            Don't run NAILGUN unit/integration tests"
  echo "  -x, --performance           Run NAILGUN performance tests"
  echo "  -p, --flake8                Run FLAKE8 and HACKING compliance check"
  echo "  -P, --no-flake8             Don't run static code checks"
  echo "  -s, --shotgun               Run SHOTGUN tests"
  echo "  -S, --no-shotgun            Don't run SHOTGUN tests"
  echo "  -t, --tests                 Run a given test files"
  echo "  -u, --upgrade               Run tests for UPGRADE system"
  echo "  -U, --no-upgrade            Don't run tests for UPGRADE system"
  echo "  -w, --webui                 Run WEB-UI tests"
  echo "  -W, --no-webui              Don't run WEB-UI tests"
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
      -x|--performance) performance_tests=1;;
      -k|--tasklib) tasklib_tests=1;;
      -K|--no-tasklib) no_tasklib_tests=1;;
      -w|--webui) webui_tests=1;;
      -W|--no-webui) no_webui_tests=1;;
      -u|--upgrade) upgrade_system=1;;
      -U|--no-upgrade) no_upgrade_system=1;;
      -s|--shotgun) shotgun_tests=1;;
      -S|--no-shotgun) no_shotgun_tests=1;;
      -p|--flake8) flake8_checks=1;;
      -P|--no-flake8) no_flake8_checks=1;;
      -l|--lint-ui) lint_ui_checks=1;;
      -L|--no-lint-ui) no_lint_ui_checks=1;;
      -t|--tests) certain_tests=1;;
      -*) testropts="$testropts $arg";;
      *) testrargs="$testrargs $arg"
    esac
  done
}

# settings
ROOT=$(dirname `readlink -f $0`)
NAILGUN_ROOT=$ROOT/nailgun
TESTRTESTS="nosetests"
FLAKE8="flake8"
PEP8="pep8"
CASPERJS="./node_modules/.bin/casperjs"
GULP="./node_modules/.bin/gulp"
LINTUI="${GULP} lint"

# test options
testrargs=
testropts="--with-timer --timer-warning=10 --timer-ok=2 --timer-top-n=10"

# nosetest xunit options
NAILGUN_XUNIT=${NAILGUN_XUNIT:-"$ROOT/nailgun.xml"}
FUELUPGRADE_XUNIT=${FUELUPGRADE_XUNIT:-"$ROOT/fuelupgrade.xml"}
SHOTGUN_XUNIT=${SHOTGUN_XUNIT:-"$ROOT/shotgun.xml"}
UI_SERVER_PORT=${UI_SERVER_PORT:-5544}
NAILGUN_PORT=${NAILGUN_PORT:-8003}
TEST_NAILGUN_DB=${TEST_NAILGUN_DB:-nailgun}
NAILGUN_CHECK_PATH=${NAILGUN_CHECK_PATH:-"/api/version"}
NAILGUN_STARTUP_TIMEOUT=${NAILGUN_STARTUP_TIMEOUT:-10}
NAILGUN_SHUTDOWN_TIMEOUT=${NAILGUN_SHUTDOWN_TIMEOUT:-3}
ARTIFACTS=${ARTIFACTS:-`pwd`/test_run}
TEST_WORKERS=${TEST_WORKERS:-0}
mkdir -p $ARTIFACTS

# disabled/enabled flags that are setted from the cli.
# used for manipulating run logic.
agent_tests=0
no_agent_tests=0
nailgun_tests=0
no_nailgun_tests=0
performance_tests=0
webui_tests=0
no_webui_tests=0
upgrade_system=0
no_upgrade_system=0
shotgun_tests=0
no_shotgun_tests=0
flake8_checks=0
no_flake8_checks=0
lint_ui_checks=0
no_lint_ui_checks=0
certain_tests=0
tasklib_tests=0
no_tasklib_tests=0


function run_tests {
  run_cleanup

  # This variable collects all failed tests. It'll be printed in
  # the end of this function as a small statistic for user.
  local errors=""

  # If tests was specified in command line then run only these tests
  if [ $certain_tests -eq 1 ]; then
    for testfile in $testrargs; do
      local testfile=`readlink -f $testfile`
      local tf=`echo $testfile | cut -d':' -f1`
      if [ ! -e $tf ]; then
          echo "ERROR: File or directory $tf not found"
          exit 1
      fi
      guess_test_run $testfile
    done
    exit
  fi

  # Enable all tests if none was specified skipping all explicitly disabled tests.
  if [[ $agent_tests -eq 0 && \
      $nailgun_tests -eq 0 && \
      $performance_tests -eq 0 && \
      $tasklib_tests -eq 0 && \
      $webui_tests -eq 0 && \
      $upgrade_system -eq 0 && \
      $shotgun_tests -eq 0 && \
      $flake8_checks -eq 0 && \
      $lint_ui_checks -eq 0 ]]; then

    if [ $no_agent_tests -ne 1 ];  then agent_tests=1;  fi
    if [ $no_nailgun_tests -ne 1 ];  then nailgun_tests=1;  fi
    if [ $no_tasklib_tests -ne 1 ];  then tasklib_tests=1;  fi
    if [ $no_webui_tests -ne 1 ];    then webui_tests=1;    fi
    if [ $no_upgrade_system -ne 1 ]; then upgrade_system=1; fi
    if [ $no_shotgun_tests -ne 1 ];  then shotgun_tests=1;  fi
    if [ $no_flake8_checks -ne 1 ];  then flake8_checks=1;  fi
    if [ $no_lint_ui_checks -ne 1 ];  then lint_ui_checks=1;  fi
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

  if [ $nailgun_tests -eq 1 ] || [ $performance_tests -eq 1 ]; then
    echo "Starting Nailgun tests..."
    run_nailgun_tests || errors+=" nailgun_tests"
  fi

  if [ $tasklib_tests -eq 1 ]; then
    echo "Starting Tasklib tests"
    run_tasklib_tests || errors+=" tasklib tests"
  fi

  if [ $webui_tests -eq 1 ]; then
    echo "Starting WebUI tests..."
    run_webui_tests || errors+=" webui_tests"
  fi

  if [ $upgrade_system -eq 1 ]; then
    echo "Starting upgrade system tests..."
    run_upgrade_system_tests || errors+=" upgrade_system_tests"
  fi

  if [ $shotgun_tests -eq 1 ]; then
    echo "Starting Shotgun tests..."
    run_shotgun_tests || errors+=" shotgun_tests"
  fi

  if [ $lint_ui_checks -eq 1 ]; then
    echo "Starting lint checks..."
    run_lint_ui || errors+=" lint_ui_checks"
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
  local options="-vv --cleandb --junit-xml $NAILGUN_XUNIT"

  if   [ $nailgun_tests -eq 1 ] && [ $performance_tests -eq 0 ]; then
    options+=" -m 'not performance' "
  elif [ $nailgun_tests -eq 0 ] && [ $performance_tests -eq 1 ]; then
    options+=" -m performance "
  fi

  prepare_artifacts $artifacts $config
  if [ $# -ne 0 ]; then
    TESTS="$@"
  fi

  if [ ! $TEST_WORKERS -eq 0 ]; then
    options+=" -n $TEST_WORKERS"
  fi

  pushd $ROOT/nailgun >> /dev/null
  # # run tests
  NAILGUN_CONFIG=$config \
  tox --recreate -epy26 -- $options $TESTS  || result=1
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
  local output=$(${GULP} build --static-dir=$COMPRESSED_STATIC_DIR 2>&1)
  if [ $? -ne 0 ]; then
    echo "$output"
    popd >> /dev/null
    exit 1
  fi
  echo "done"

  # run js testcases
  local server_log=`mktemp /tmp/test_nailgun_ui_server.XXXX`
  local result=0
  local pid

  for testcase in $TESTS; do

    dropdb $config
    syncdb $config true

    run_server $SERVER_PORT $server_log $config || \
      { echo 'Failed to start Nailgun'; return 1; }

    SERVER_PORT=$SERVER_PORT \
    ${CASPERJS} test --includes="$TESTS_DIR/helpers.js" --fail-fast "$testcase"
    if [ $? -ne 0 ]; then
      result=1
      break
    fi

    kill_server $SERVER_PORT

  done

  rm $server_log
  popd >> /dev/null

  return $result
}


# Run tests for fuel upgrade system
#
# Arguments:
#
#   $@ -- tests to be run; with no arguments all tests will be run
function run_upgrade_system_tests {
  local UPGRADE_TESTS="$ROOT/fuel_upgrade_system/fuel_upgrade/fuel_upgrade/tests/"
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

function run_tasklib_tests {
  local result=0

  pushd $ROOT/tasklib >> /dev/null

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
  run_flake8_subproject tasklib && \
  run_flake8_subproject fuelmenu && \
  run_flake8_subproject network_checker && \
  run_flake8_subproject fuel_upgrade_system/fuel_upgrade && \
  run_flake8_subproject fuel_upgrade_system/fuel_package_updates && \
  run_flake8_subproject shotgun || result=1
  return $result
}


# Check javascript files with `jshint`. It's necessary to run it inside
# `nailgun` folder, so we temporary change current dir.
function run_lint_ui {
  pushd $ROOT/nailgun >> /dev/null

  local result=0
  ${LINTUI} || result=1

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
#
# Sends SIGING to running Nailgun
function kill_server() {
  local server_port=$1

  # kill old server instance if exists
  local pid=$(lsof -ti tcp:$server_port)
  if [[ -n "$pid" ]]; then
    kill $pid
    sleep $NAILGUN_SHUTDOWN_TIMEOUT
  fi
}


# Arguments:
#
#   $1 -- server port
#   $1 -- path to log file
#   $2 -- path to the server config
#
# Returns: a server pid, that you have to close manually
function run_server() {
  local server_port=$1
  local server_log=$2
  local server_config=$3

  local run_server_cmd="\
    python manage.py run \
    --port=$server_port \
    --config=$server_config \
    --fake-tasks \
    --fake-tasks-tick-count=80 \
    --fake-tasks-tick-interval=1"

  kill_server $server_port

  # run new server instance
  pushd $NAILGUN_ROOT > /dev/null
  tox -evenv -- $run_server_cmd >> $server_log 2>&1 &
  if [[ $? -ne 0 ]]; then
    echo "CRITICAL: Nailgun failed to start."
    echo "          Server log is stored in $server_log"
    return 1
  fi
  popd > /dev/null

  # wait for server availability
  which curl > /dev/null

  if [[ $? -eq 0 ]]; then
    local num_retries=$((NAILGUN_STARTUP_TIMEOUT * 10))
    local check_url="http://0.0.0.0:${server_port}${NAILGUN_CHECK_PATH}"
    local i=0

    while true; do
      # Fail if number of retries exeeded
      if [[ $i -gt $((num_retries + 1)) ]]; then

        # Report, if Nailgun failed to start before the timeout.
        echo "CRITICAL: Nailgun failed to start before the timeout."
        echo "          It's possible to increase waiting time by settings the required"
        echo "          number of seconds in NAILGUN_STARTUP_TIMEOUT environment variable."

        return 1
      fi

      local http_code=$(curl -s -w %{http_code} -o /dev/null $check_url)

      if [[ "$http_code" = "200" ]]; then return 0; fi

      sleep 0.1
      i=$((i + 1))
    done

    kill_server $server_port
    return 1;

  else
    echo "WARNING: Cannot check whether Nailgun is running bacause curl is not available."
    echo "         Waiting $NAILGUN_STARTUP_TIMEOUT in order to let it start properly."
    echo "         It's possible to increase waiting time by settings the required number of"
    echo "         seconds in NAILGUN_STARTUP_TIMEOUT environment variable."
    sleep $NAILGUN_STARTUP_TIMEOUT
    lsof -ti tcp:$server_port

    return $?
  fi
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
