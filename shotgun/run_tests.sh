#!/bin/bash

function usage {
  echo "Usage: $0 [OPTION]..."
  echo "Run tests"
  echo ""
  echo "  -p, --flake8             Just run flake8 and HACKING compliance check"
  echo "  -f, --fail-first         Nosetests will stop on first error"
  echo "  -u, --unit               Just run unit tests"
  echo "  -x, --xunit              Generate reports (useful in Jenkins environment)"
  echo "  -P, --no-flake8          Don't run static code checks"
  echo "  -c, --clean              Only clean *.log, *.json, *.pyc, *.pid files, doesn't run tests"
  echo "  -h, --help               Print this usage message"
  echo ""
  echo "By default it runs tests and flake8 check."
  exit
}

function process_option {
  case "$1" in
    -h|--help) usage;;
    -p|--flake8) just_flake8=1;;
    -f|--fail-first) fail_first=1;;
    -P|--no-flake8) no_flake8=1;;
    -u|--unit) unit_tests=1;;
    -x|--xunit) xunit=1;;
    -c|--clean) clean=1;;
    -*) noseopts="$noseopts $1";;
    *) noseargs="$noseargs $1"
  esac
}

just_flake8=0
no_flake8=0
fail_first=0
unit_tests=0
xunit=0
clean=0
default_noseargs=""
noseargs="$default_noseargs"
noseopts=

for arg in "$@"; do
  process_option $arg
done

function clean {
  echo "cleaning *.pyc, *.json, *.log, *.pid files"
  find . -type f -name "*.pyc" -delete
  rm -f *.json
  rm -f *.log
  rm -f *.pid
}

if [ $clean -eq 1 ]; then
  clean
  exit 0
fi

# If enabled, tell nose to create xunit report
if [ $xunit -eq 1 ]; then
    noseopts=${noseopts}" --with-xunit"
fi

if [ $fail_first -eq 1 ]; then
    noseopts=${noseopts}" --stop"
fi


function run_flake8 {
  # H302 - "import only modules. does not import a module" requires to import only modules and not functions
  # H802 - first line of git commit commentary should be less than 50 characters
  # __init__.py - excluded because it doesn't comply with pep8 standard
  flake8 --exclude=__init__.py --ignore=H302,H802 --show-source --show-pep8 --count . || return 1
  echo "Flake8 check passed successfully."
}

if [ $just_flake8 -eq 1 ]; then
    run_flake8 || exit 1
    exit
fi


function run_tests {
  clean
  [ -z "$noseargs" ] && test_args=. || test_args="$noseargs"
  stderr=$(nosetests $noseopts $test_args --verbosity=2 3>&1 1>&2 2>&3 | tee /dev/stderr)
}


function run_unit_tests {
    noseargs="shotgun/test"
    run_tests
}

if [ $unit_tests -eq 1 ]; then
    run_unit_tests || exit 1
    exit
fi

errors=''

run_tests || errors+=' unittests'

if [ "$noseargs" == "$default_noseargs" ]; then
  if [ $no_flake8 -eq 0 ]; then
    run_flake8 || errors+=' flake8'
  fi
fi

if [ -n "$errors" ]; then
  echo Failed tests: $errors
  exit 1
fi
