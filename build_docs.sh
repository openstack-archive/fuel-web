#!/bin/sh

# config

VENV='fuel-web-venv'
VIEW='0'
HTML='docs/_build/html/index.html'
SINGLEHTML='docs/_build/singlehtml/index.html'
EPUB='docs/_build/epub/Fuel.epub'
LATEXPDF='docs/_build/latex/fuel.pdf'
PDF='docs/_build/pdf/Fuel.pdf'

# functions

check_if_debian() {
  test -f '/etc/debian_version'
  return $?
}

check_if_redhat() {
  test -f '/etc/redhat-release'
  return $?
}

check_java_present() {
  which java 1>/dev/null 2>/dev/null
  return $?
}

check_latex_present() {
  which pdflatex 1>/dev/null 2>/dev/null
  return $?
}

cd_to_dir() {
  FILE="${0}"
  DIR=`dirname "${FILE}"`
  cd "${DIR}"
  if [ $? -gt 0 ]; then
    echo "Cannot cd to dir ${DIR}!"
    exit 1
  fi
}

redhat_prepare_packages() {
  # prepare postgresql utils and dev packages
  # required to build psycopg Python pgsql library
  sudo yum -y install postgresql postgresql-devel

  # prepare python tools
  sudo yum -y install -y python-devel make python-pip python-virtualenv
}

debian_prepare_packages() {
  # prepare postgresql utils and dev packages
  # required to build psycopg Python pgsql library
  sudo apt-get -y install postgresql postgresql-server-dev-all

  # prepare python tools
  sudo apt-get -y install -y python-dev python-pip make python-virtualenv
}

prepare_packages() {
  if check_if_debian; then
    debian_prepare_packages
  elif check_if_redhat; then
    redhat_prepare_packages
  else
    echo 'OS is not supported!'
    exit 1
  fi
}

prepare_venv() {
  # activate venv
  virtualenv "${VENV}"  # you can use any name instead of 'fuel'
  . "${VENV}/bin/activate" # command selects the particular environment
  # install dependencies
  pip install ./shotgun  # this fuel project is listed in setup.py requirements
  pip install -r 'nailgun/test-requirements.txt'
}

view_file() {
  xdg-open "${1}"
}

build_html() {
  make -C docs html
  if [ "${VIEW}" = '1' ]; then
    view_file "${HTML}"
  fi
}

build_singlehtml() {
  make -C docs singlehtml
  if [ "${VIEW}" = '1' ]; then
    view_file "${SINGLEHTML}"
  fi
}

build_latexpdf() {
  check_latex_present
  if [ $? -gt 0 ]; then
    echo 'You need to install LaTeX if you want to build PDF!'
    exit 1
  fi
  make -C docs latexpdf
  if [ "${VIEW}" = '1' ]; then
    view_file "${LATEXPDF}"
  fi
}

build_epub() {
  make -C docs epub
  if [ "${VIEW}" = '1' ]; then
    view_file "${EPUB}"
  fi
}

build_pdf() {
  make -C docs pdf
  if [ "${VIEW}" = '1' ]; then
    view_file "${PDF}"
  fi
}

clear_build() {
  make -C docs clean
}

show_help() {
cat <<EOF
Documentation build helper
-o - Open generated documentation after build
-c - Clear the build directory
-f - Documentation format [html,signlehtml,pdf,latexpdf,epub]
EOF
}

# MAIN

while getopts ":ohcf:" opt; do
  case $opt in
    o)
      VIEW='1'
      ;;
    h)
      show_help
      exit 0
      ;;
    c)
      clear_build
      exit 0
      ;;
    f)
      FORMAT="${OPTARG}"
      ;;
    \?)
      echo "Invalid option: -$OPTARG" >&2
      show_help
      exit 1
      ;;
  esac
done

check_java_present
if [ $? -gt 0 ]; then
  echo 'There is no Java installed!'
  exit 1
fi

cd_to_dir

prepare_packages
prepare_venv

if [ "${FORMAT}" = '' ]; then
  FORMAT='html'
fi

case "${FORMAT}" in
html)
  build_html
  ;;
singlehtml)
  build_singlehtml
  ;;
pdf)
  build_pdf
  ;;
latexpdf)
  build_latexpdf
  ;;
epub)
  build_epub
  ;;
*)
  echo "Format ${FORMAT} is not supported!"
  exit 1
  ;;
esac
