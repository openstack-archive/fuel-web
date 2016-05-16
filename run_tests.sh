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
  echo "  -x, --performance           Run NAILGUN performance tests"
  echo ""
  echo "Note: with no options specified, the script will try to run all available"
  echo "      tests with all available checks."
  exit
}

if [ $# -lt 1 ]; then
    usage
fi


function process_options {
  for arg in $@; do
    case "$arg" in
      -h|--help) usage;;
      -x|--performance) performance_tests=1;;
      *) usage;;
    esac
  done
}


function run_tests {
  if [ $performance_tests -eq 1 ]; then
    echo "Starting Nailgun performance tests..."
    tox -eperformance || errors+=" nailgun_tests"
  fi

  if [ -n "$errors" ]; then
    echo Failed tests: $errors
    exit 1
  fi

  exit
}

process_options $@
run_tests
