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
  echo "  -h, --help                  Print this usage message"
  echo "  -n, --nailgun               Run NAILGUN unit/integration tests"
  echo "  -N, --no-nailgun            Don't run NAILGUN unit/integration tests"
  echo "  -x, --performance           Run NAILGUN performance tests"
  echo "  -p, --flake8                Run FLAKE8 and HACKING compliance check"
  echo "  -P, --no-flake8             Don't run static code checks"
  echo "  -t, --tests                 Run a given test files"
  echo "  -w, --webui                 Run all UI tests"
  echo "  -W, --no-webui              Don't run all UI tests"
  echo "  -e, --extensions            Run EXTENSIONS unit/integration tests"
  echo "  -E, --no-extensions         Don't run EXTENSIONS unit/integration tests"
  echo "      --ui-lint               Run UI linting tasks"
  echo "      --no-ui-lint            Don't run UI linting tasks"
  echo "      --ui-license            Run UI license checks"
  echo "      --no-ui-license         Don't run UI license checks"
  echo "      --ui-unit               Run UI unit tests"
  echo "      --no-ui-unit            Don't run UI unit tests"
  echo "      --ui-func               Run UI functional tests"
  echo "      --no-ui-func            Don't run UI functional tests"
  echo "      --no-ui-compression     Skip UI compression for UI functional tests"
  echo "      --no-nailgun-start      Skip Nailgun start for UI functional tests"
  echo ""
  echo "Note: with no options specified, the script will try to run all available"
  echo "      tests with all available checks."
  exit
}


function process_options {
  for arg in $@; do
    case "$arg" in
      -h|--help) usage;;
      -n|--nailgun) nailgun_tests=1;;
      -N|--no-nailgun) no_nailgun_tests=1;;
      -x|--performance) performance_tests=1;;
      -p|--flake8) flake8_checks=1;;
      -P|--no-flake8) no_flake8_checks=1;;
      -w|--webui) ui_lint_checks=1; ui_license_checks=1; ui_unit_tests=1; ui_func_tests=1;;
      -W|--no-webui) no_ui_lint_checks=1; no_ui_license_checks=1; no_ui_unit_tests=1; no_ui_func_tests=1;;
      -e|--extensions) extensions_tests=1;;
      -E|--no-extensions) no_extensions_tests=1;;
      --ui-lint) ui_lint_checks=1;;
      --no-ui-lint) no_ui_lint_checks=1;;
      --ui-license) ui_license_checks=1;;
      --no-ui-license) no_ui_license_checks=1;;
      --ui-unit) ui_unit_tests=1;;
      --no-ui-unit) no_ui_unit_tests=1;;
      --ui-func) ui_func_tests=1;;
      --no-ui-func) no_ui_func_tests=1;;
      --no-ui-compression) no_ui_compression=1;;
      --no-nailgun-start) no_nailgun_start=1;;
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
GULP="./node_modules/.bin/gulp"
TOXENV=${TOXENV:-py27}

# test options
testrargs=
testropts="--with-timer --timer-warning=10 --timer-ok=2 --timer-top-n=10"

# nosetest xunit options
NAILGUN_XUNIT=${NAILGUN_XUNIT:-"$ROOT/nailgun.xml"}
EXTENSIONS_XUNIT=${EXTENSIONS_XUNIT:-"$ROOT/extensions.xml"}
NAILGUN_PORT=${NAILGUN_PORT:-5544}
TEST_NAILGUN_DB=${TEST_NAILGUN_DB:-nailgun}
NAILGUN_CHECK_PATH=${NAILGUN_CHECK_PATH:-"/api/version"}
NAILGUN_STARTUP_TIMEOUT=${NAILGUN_STARTUP_TIMEOUT:-10}
NAILGUN_SHUTDOWN_TIMEOUT=${NAILGUN_SHUTDOWN_TIMEOUT:-3}
ARTIFACTS=${ARTIFACTS:-`pwd`/test_run}
TEST_WORKERS=${TEST_WORKERS:-0}
mkdir -p $ARTIFACTS

# disabled/enabled flags that are set from the cli.
# used for manipulating run logic.
nailgun_tests=0
no_nailgun_tests=0
performance_tests=0
flake8_checks=0
no_flake8_checks=0
ui_lint_checks=0
no_ui_lint_checks=0
ui_license_checks=0
no_ui_license_checks=0
ui_unit_tests=0
no_ui_unit_tests=0
ui_func_tests=0
no_ui_func_tests=0
extensions_tests=0
no_extensions_tests=0
certain_tests=0
no_ui_compression=0
no_nailgun_start=0

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
  if [[ $nailgun_tests -eq 0 && \
      $performance_tests -eq 0 && \
      $ui_lint_checks -eq 0 && \
      $ui_license_checks -eq 0 && \
      $ui_unit_tests -eq 0 && \
      $ui_func_tests -eq 0 && \
      $extensions_tests -eq 0 && \
      $flake8_checks -eq 0 ]]; then

    if [ $no_nailgun_tests -ne 1 ];      then nailgun_tests=1;     fi
    if [ $no_ui_lint_checks -ne 1 ];     then ui_lint_checks=1;    fi
    if [ $no_ui_license_checks -ne 1 ];  then ui_license_checks=1; fi
    if [ $no_ui_unit_tests -ne 1 ];      then ui_unit_tests=1;     fi
    if [ $no_ui_func_tests -ne 1 ];      then ui_func_tests=1;     fi
    if [ $no_flake8_checks -ne 1 ];      then flake8_checks=1;     fi
    if [ $no_extensions_tests -ne 1 ];   then extensions_tests=1;  fi

  fi

  # Run all enabled tests
  if [ $flake8_checks -eq 1 ]; then
    echo "Starting Flake8 tests..."
    run_flake8 || errors+=" flake8_checks"
  fi

  if [ $nailgun_tests -eq 1 ] || [ $performance_tests -eq 1 ]; then
    echo "Starting Nailgun tests..."
    run_nailgun_tests || errors+=" nailgun_tests"
  fi

  if [ $ui_lint_checks -eq 1 ]; then
    echo "Starting UI lint checks..."
    run_lint_ui || errors+=" ui_lint_checks"
  fi

  if [ $ui_license_checks -eq 1 ]; then
    echo "Starting UI license checks..."
    run_ui_license_checks || errors+=" ui_license_checks"
  fi

  if [ $ui_unit_tests -eq 1 ]; then
    echo "Starting UI unit tests..."
    run_ui_unit_tests || errors+=" ui_unit_tests"
  fi

  if [ $ui_func_tests -eq 1 ]; then
    echo "Starting UI functional tests..."
    run_ui_func_tests || errors+=" ui_func_tests"
  fi

  if [ $extensions_tests -eq 1 ]; then
    echo "Starting Extensions tests..."
    run_extensions_tests || errors+=" extensions_tests"
  fi

  # print failed tests
  if [ -n "$errors" ]; then
    echo Failed tests: $errors
    exit 1
  fi

  exit
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
  TOXENV=$TOXENV \
  NAILGUN_CONFIG=$config \
  tox -- $options $TESTS  || result=1
  popd >> /dev/null
  return $result
}

# Run UI unit tests.
#
function run_ui_unit_tests {
  local result=0

  pushd $ROOT/nailgun >> /dev/null

  npm run unit-tests || result=1

  popd >> /dev/null

  return $result
}

# Run UI functional tests.
#
# Arguments:
#
#   $@ -- tests to be run; with no arguments all tests will be run
function run_ui_func_tests {
  local TESTS_DIR=$ROOT/nailgun/static/tests/functional
  local TESTS=$TESTS_DIR/test_*.js
  local artifacts=$ARTIFACTS/ui_func
  local config=$artifacts/test.yaml
  prepare_artifacts $artifacts $config
  local COMPRESSED_STATIC_DIR=$artifacts/static_compressed

  if [ $# -ne 0 ]; then
    TESTS=$@
  fi

  pushd $ROOT/nailgun >> /dev/null

  if [ $no_ui_compression -ne 1 ]; then
    echo "Compressing UI... "
    ${GULP} build --no-sourcemaps --static-dir=$COMPRESSED_STATIC_DIR
    if [ $? -ne 0 ]; then
      popd >> /dev/null
      return 1
    fi
  else
    echo "Using compressed UI from $COMPRESSED_STATIC_DIR"
    if [ ! -f "$COMPRESSED_STATIC_DIR/index.html" ]; then
      echo "Cannot find compressed UI. Don't use --no-ui-compression key"
      return 1
    fi
  fi

  # run js testcases
  local server_log=`mktemp /tmp/test_nailgun_ui_server.XXXX`
  local result=0
  local pid

  for testcase in $TESTS; do
    if [ $no_nailgun_start -ne 1 ]; then
      dropdb $config
      syncdb $config true

      run_server $NAILGUN_PORT $server_log $config || \
        { echo 'Failed to start Nailgun'; return 1; }
    fi

    SERVER_PORT=$NAILGUN_PORT \
    ARTIFACTS=$artifacts \
    ${GULP} functional-tests --suites=$testcase
    if [ $? -ne 0 ]; then
      result=1
      break
    fi

    if [ $no_nailgun_start -ne 1 ]; then
      kill_server $NAILGUN_PORT
    fi
  done

  rm $server_log
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


# Run tests for Nailgun extensions
function run_extensions_tests {
  local EXTENSIONS_PATH="$ROOT/nailgun/nailgun/extensions/"
  local NAILGUN_PATH="$ROOT/nailgun/"
  local result=0

  pushd "${NAILGUN_PATH}" >> /dev/null
  TOXENV=$TOXENV \
  tox -- -vv "${EXTENSIONS_PATH}" --junit-xml $EXTENSIONS_XUNIT || result=1
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
  run_flake8_subproject nailgun && \
  return $result
}


# Lints Javascript and style files. It's necessary to run it inside
# `nailgun` folder, so we temporary change current dir.
function run_lint_ui {
  pushd $ROOT/nailgun >> /dev/null

  local result=0
  npm run lint || result=1

  popd >> /dev/null
  return $result
}


# Checks UI dependency licenses. It's necessary to run it inside
# `nailgun` folder, so we temporary change current dir.
function run_ui_license_checks {
  pushd $ROOT/nailgun >> /dev/null

  local result=0
  npm run license || result=1

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
    NAILGUN_CONFIG=$config tox -evenv -- python manage.py loaddata nailgun/fixtures/sample_environment.json > /dev/null
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

  if [[ $1 == *functional* && $1 == *.js ]]; then
    run_ui_func_tests $1
  else
    run_nailgun_tests $1
  fi
}


# parse command line arguments and run the tests
process_options $@
run_tests
