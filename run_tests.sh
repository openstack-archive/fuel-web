#!/bin/bash

function usage {
  echo "Usage: $0 [OPTION]..."
  echo "Run tests"
  echo ""
  echo "  -p, --flake8             Just run flake8 and HACKING compliance check"
  echo "  -f, --fail-first         Nosetests will stop on first error"
  echo "  -j, --jslint             Just run JSLint"
  echo "  -u, --ui-tests           Just run UI tests"
  echo "  -i, --integration        Just run integration tests"
  echo "  -C, --cli                Just run fuel-cli tests"
  echo "  -u, --unit               Just run unit tests"
  echo "  -x, --xunit              Generate reports (useful in Jenkins environment)"
  echo "  -P, --no-flake8          Don't run static code checks"
  echo "  -J, --no-jslint          Don't run JSLint"
  echo "  -U, --no-ui-tests        Don't run UI tests"
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
    -j|--jslint) just_jslint=1;;
    -u|--ui-tests) just_ui_tests=1;;
    -P|--no-flake8) no_flake8=1;;
    -J|--no-jslint) no_jslint=1;;
    -U|--no-ui-tests) no_ui_tests=1;;
    -I|--integration) integration_tests=1;;
    -n|--unit) unit_tests=1;;
    -C|--cli) cli_tests=1;;
    -x|--xunit) xunit=1;;
    -c|--clean) clean=1;;
    ui_tests*) ui_test_files="$ui_test_files $1";;
    -*) noseopts="$noseopts $1";;
    *) noseargs="$noseargs $1"
  esac
}

just_flake8=0
no_flake8=0
fail_first=0
just_jslint=0
no_jslint=0
just_ui_tests=0
no_ui_tests=0
integration_tests=0
cli_tests=0
unit_tests=0
xunit=0
clean=0
ui_test_files=
default_noseargs="--with-timer"
noseargs="$default_noseargs"
noseopts=

for arg in "$@"; do
  process_option $arg
done

if [ -n "$ui_test_files" ]; then
    just_ui_tests=1
fi

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
  flake_status=0
  flake8 --exclude=__init__.py,docs --ignore=H302,H802 --show-source --show-pep8 --count . || flake_status=1
  pep8 --exclude=welcome.py docs || flake_status=1
  [[ $flake_status = 0 ]] || return 1
  echo "Flake8 check passed successfully."
}

if [ $just_flake8 -eq 1 ]; then
    run_flake8 || exit 1
    exit
fi

function run_jslint {
    which jslint > /dev/null
    if [ $? -ne 0 ]; then
        echo "JSLint is not installed; install by running:"
        echo "sudo apt-get install npm"
        echo "sudo npm install -g jslint"
        return 1
    fi
    (
    cd nailgun
    jsfiles=$(find static/js -type f | grep -v ^static/js/libs/ | grep \\.js$)
    jslint_predef=(requirejs require define app Backbone $ _ alert confirm)
    jslint_options="$(echo ${jslint_predef[@]} | sed 's/^\| / --predef=/g') --browser=true --nomen=true --eqeq=true --vars=true --white=true --es5=false"
    jslint $jslint_options $jsfiles
    ) || return 1
}

if [ $just_jslint -eq 1 ]; then
    run_jslint || exit 1
    exit
fi

function run_ui_tests {
    which casperjs > /dev/null
    if [ $? -ne 0 ]; then
        echo "CasperJS is not installed; install by running:"
        echo "sudo apt-get install phantomjs"
        echo "cd ~"
        echo "git clone git://github.com/n1k0/casperjs.git"
        echo "cd casperjs"
        echo "git checkout tags/1.0.0-RC4"
        echo "sudo ln -sf \`pwd\`/bin/casperjs /usr/local/bin/casperjs"
        return 1
    fi
    (
    cd nailgun
    ui_tests_dir=ui_tests
    if [ -z "$ui_test_files" ]; then
        ui_test_files=$ui_tests_dir/test_*.js
    fi
    result=0

    echo -n "Compressing UI... "
    compressed_static_dir=/tmp/static_compressed
    rm -rf $compressed_static_dir && mkdir -p $compressed_static_dir
    r.js -o build.js dir=$compressed_static_dir > /dev/null
    if [ $? -ne 0 ]; then
        echo "Failed!"
        exit 1
    fi
    echo "Done"
    test_server_config=$compressed_static_dir/settings.yaml
    echo -e "DEVELOPMENT: 0\nSTATIC_DIR: '$compressed_static_dir'" > $compressed_static_dir/settings.yaml
    test_server_port=5544
    test_server_cmd="./manage.py run --port=$test_server_port --config=$test_server_config --fake-tasks --fake-tasks-tick-count=80 --fake-tasks-tick-interval=1"
    old_server_pid=`ps aux | grep "$test_server_cmd" | grep -v grep | awk '{ print $2 }'`
    if [ -n "$old_server_pid" ]; then
        kill $old_server_pid
        echo -n "Killing old test server... "
        sleep 5
    fi
    test_server_log_file=`tempfile`
    for test_file in $ui_test_files; do
        echo -n "Starting test server for $test_file ... "
        ./manage.py dropdb > /dev/null
        ./manage.py syncdb > /dev/null
        ./manage.py loaddefault > /dev/null
        $test_server_cmd >> $test_server_log_file 2>&1 &
        server_pid=$!
        which nc > /dev/null
        if [ $? -eq 0 ]; then
            # nc is available, use it to check test server readiness
            for i in {1..50}; do
                nc -vz localhost $test_server_port 2> /dev/null
                if [ $? -eq 0 ]; then break; fi
                sleep 0.1
            done
        else
            # nc is not available, use sleep
            sleep 5
        fi
        kill -0 $server_pid 2> /dev/null
        if [ $? -eq 0 ]; then
            echo "Test server started"
            casperjs test --includes=$ui_tests_dir/helpers.js --fail-fast $test_file
            result=$(($result + $?))
            kill $server_pid
            wait $server_pid 2> /dev/null
        else
            echo "Test server failed to start!"
            cat $test_server_log_file
            result=1
            break
        fi
    done
    ./manage.py dropdb >> /dev/null
    rm $test_server_log_file
    return $result
    )
}

if [ $just_ui_tests -eq 1 ]; then
    run_ui_tests || exit 1
    exit
fi

function run_nailgun_tests {
  clean
  (
  cd nailgun
  ./manage.py dropdb > /dev/null
  ./manage.py syncdb > /dev/null
  [ -z "$noseargs" ] && test_args=. || test_args="$noseargs"
  stderr=$(nosetests $noseopts $test_args --verbosity=2 3>&1 1>&2 2>&3 | tee /dev/stderr)
  )
# TODO: uncomment after cluster deletion issue fix
#  if [[ "$stderr" =~ "Exception" ]]; then
#    echo "Tests executed with errors!"
#    exit 1
#  fi
}

function run_cli_tests {
    (
    cd nailgun
    result=0
    test_server_port=8003
    test_server_cmd="./manage.py run --port=$test_server_port --fake-tasks"
    old_server_pid=`ps aux | grep "$test_server_cmd" | grep -v grep | awk '{ print $2 }'`
    if [ -n "$old_server_pid" ]; then
        kill $old_server_pid
        echo -n "Killing old test server... "
        sleep 5
    fi
    test_server_log_file=`tempfile`
    # for test_file in $ui_test_files; do
    echo -n "Starting test server ... "
    ./manage.py dropdb > /dev/null
    ./manage.py syncdb > /dev/null
    ./manage.py loaddefault > /dev/null
    $test_server_cmd >> $test_server_log_file 2>&1 &
    server_pid=$!
    which nc > /dev/null
    if [ $? -eq 0 ]; then
        # nc is available, use it to check test server readiness
        for i in {1..50}; do
            nc -vz localhost $test_server_port 2> /dev/null
            if [ $? -eq 0 ]; then break; fi
            sleep 0.1
        done
    else
        # nc is not available, use sleep
        sleep 5
    fi
    kill -0 $server_pid 2> /dev/null
    if [ $? -eq 0 ]; then
        echo "Test server started"
        clean
        test_args="../fuelclient/tests"
        stderr=$(nosetests $noseopts $test_args --verbosity=2 3>&1 1>&2 2>&3 | tee /dev/stderr)
        result=$(($result + $?))
        kill $server_pid
        wait $server_pid 2> /dev/null
    else
        echo "Test server failed to start!"
        cat $test_server_log_file
        result=1
        break
    fi

    ./manage.py dropdb >> /dev/null
    rm $test_server_log_file
    return $result
    )
}

if [ $cli_tests -eq 1 ]; then
    run_cli_tests || exit 1
    exit
fi

function run_integration_tests {
    noseargs="nailgun/test/integration"
    run_nailgun_tests
}

if [ $integration_tests -eq 1 ]; then
    run_integration_tests || exit 1
    exit
fi

function run_unit_tests {
    nosetests $noseopts $test_args --verbosity=2 nailgun/nailgun/test/unit #shotgun
}

if [ $unit_tests -eq 1 ]; then
    run_unit_tests || exit 1
    exit
fi

errors=''

trap drop_db INT

function drop_db {
  nailgun/manage.py dropdb >> /dev/null
  exit 1
}

run_unit_tests || errors+=' unittests'

run_cli_tests || errors+=' clitests'

run_integration_tests || errors+=' integration'

if [ $no_flake8 -eq 0 ]; then
  run_flake8 || errors+=' flake8'
fi
if [ $no_jslint -eq 0 ]; then
  run_jslint || errors+=' jslint'
fi
if [ $no_ui_tests -eq 0 ]; then
  run_ui_tests || errors+=' ui-tests'
fi

if [ -n "$errors" ]; then
  echo Failed tests: $errors
  exit 1
fi
