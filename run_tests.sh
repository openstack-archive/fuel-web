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
  echo "  -e, --extensions            Run EXTENSIONS unit/integration tests"
  echo "  -E, --no-extensions         Don't run EXTENSIONS unit/integration tests"
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
      -e|--extensions) extensions_tests=1;;
      -E|--no-extensions) no_extensions_tests=1;;
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
TOXENV=${TOXENV:-py27}

# test options
testrargs=
testropts="--with-timer --timer-warning=10 --timer-ok=2 --timer-top-n=10"

# nosetest xunit options
NAILGUN_XUNIT=${NAILGUN_XUNIT:-"$ROOT/nailgun.xml"}
EXTENSIONS_XUNIT=${EXTENSIONS_XUNIT:-"$ROOT/extensions.xml"}
TEST_NAILGUN_DB=${TEST_NAILGUN_DB:-nailgun}
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
extensions_tests=0
no_extensions_tests=0
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
      local tf=`echo $testfile | cut -d':' -f1`
      if [ ! -e $tf ]; then
          echo "ERROR: File or directory $tf not found"
          exit 1
      fi
      run_nailgun_tests $testfile
    done
    exit
  fi

  # Enable all tests if none was specified skipping all explicitly disabled tests.
  if [[ $nailgun_tests -eq 0 && \
      $performance_tests -eq 0 && \
      $extensions_tests -eq 0 && \
      $flake8_checks -eq 0 ]]; then

    if [ $no_nailgun_tests -ne 1 ];    then nailgun_tests=1;  fi
    if [ $no_flake8_checks -ne 1 ];    then flake8_checks=1;  fi
    if [ $no_extensions_tests -ne 1 ]; then extensions_tests=1; fi

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
  tox -- $options nailgun/test/performance/integration/test_cluster.py || result=1
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


# Remove temporary files. No need to run manually, since it's
# called automatically in `run_tests` function.
function run_cleanup {
  find . -type f -name "*.pyc" -delete
  rm -f *.log
  rm -f *.pid
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

# parse command line arguments and run the tests
process_options $@
run_tests
