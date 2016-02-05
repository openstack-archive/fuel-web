#!/bin/bash

#    Copyright 2016 Mirantis, Inc.
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
  echo "Run Fuel UI functional tests"
  echo ""
  echo "  -h, --help                  Print this usage message"
  echo "      --no-ui-compression     Skip UI compression"
  echo "      --no-nailgun-start      Skip Nailgun start"
  exit
}

no_ui_compression=0
no_nailgun_start=0
tests=

function process_options {
  for arg in $@; do
    case "$arg" in
      -h|--help) usage;;
      --no-ui-compression) no_ui_compression=1;;
      --no-nailgun-start) no_nailgun_start=1;;
      -*);;
      *) tests="$tests $arg"
    esac
  done
}

FUEL_WEB_ROOT=$(realpath $(dirname $0)/..)
NAILGUN_ROOT=$FUEL_WEB_ROOT/nailgun

. ${NAILGUN_ROOT}/tools/env_functions.sh

ARTIFACTS=${ARTIFACTS:-`pwd`/test_run}
mkdir -p $ARTIFACTS

NAILGUN_CONFIG=$ARTIFACTS/test.yaml
NAILGUN_LOGS=$ARTIFACTS
NAILGUN_STATIC=$ARTIFACTS/static
NAILGUN_TEMPLATES=$NAILGUN_STATIC

NAILGUN_PORT=${NAILGUN_PORT:-5544}
NAILGUN_START_MAX_WAIT_TIME=${NAILGUN_START_MAX_WAIT_TIME:-30}

NAILGUN_DB=${NAILGUN_DB:-nailgun}
NAILGUN_DB_HOST=${NAILGUN_DB_HOST:-localhost}
NAILGUN_DB_PORT=${NAILGUN_DB_PORT:-5432}
NAILGUN_DB_USER=${NAILGUN_DB_USER:-nailgun}
NAILGUN_DB_PW=${NAILGUN_DB_PW:-nailgun}

DB_ROOT=${DB_ROOT:-postgres}

NAILGUN_FIXTURE_FILES="${NAILGUN_ROOT}/nailgun/fixtures/sample_environment.json ${NAILGUN_ROOT}/nailgun/fixtures/sample_plugins.json"

NAILGUN_CHECK_URL='/api/version'


# Run UI functional tests.
#
# Arguments:
#
#   $@ -- tests to be run; with no arguments all tests will be run
function run_ui_func_tests {
  local GULP="./node_modules/.bin/gulp"
  local TESTS_DIR=static/tests/functional # FIXME(vkramskikh): absolute path should be used
  local TESTS=$TESTS_DIR/test_*.js

  prepare_nailgun_env

  if [ $# -ne 0 ]; then
    TESTS=$@
  fi

  if [ $no_ui_compression -ne 1 ]; then
    echo "Compressing UI... "
    ${GULP} build --no-sourcemaps --extra-entries=sinon --static-dir=$NAILGUN_STATIC
    if [ $? -ne 0 ]; then
      return 1
    fi
  else
    echo "Using compressed UI from $NAILGUN_STATIC"
    if [ ! -f "$NAILGUN_STATIC/index.html" ]; then
      echo "Cannot find compressed UI. Don't use --no-ui-compression key"
      return 1
    fi
  fi

  if [ $no_nailgun_start -ne 1 ]; then
    cleanup_server
  fi

  local result=0

  for testcase in $TESTS; do
    dropdb # FIXME(vkramskikh): tools should be used instead

    local server_log=`mktemp /tmp/test_nailgun_ui_server.XXXX`
    if [ $no_nailgun_start -ne 1 ]; then
      prepare_server
    fi

    SERVER_PORT=$NAILGUN_PORT \
    ARTIFACTS=$ARTIFACTS \
    ${GULP} functional-tests --suites=$testcase || result=1

    if [ $no_nailgun_start -ne 1 ]; then
      cleanup_server
    fi

    if [ $result -ne 0 ]; then
      mv $server_log $ARTIFACTS/app.log
      break
    fi
    rm $server_log
  done

  return $result
}


function dropdb {
  pushd $NAILGUN_ROOT > /dev/null
  tox -evenv -- python manage.py dropdb > /dev/null
  popd > /dev/null
}


# parse command line arguments and run the tests
process_options $@
run_ui_func_tests $tests
