#!/bin/sh

# config

VENV='fuel-web-venv'
VIEW='0'
HTML='docs/_build/html/index.html'
SINGLEHTML='docs/_build/singlehtml/index.html'
EPUB='docs/_build/epub/Fuel.epub'
PDF='docs/_build/latex/scaffold.pdf'

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
  sudo yum -y install -y python-devel python-setuptools make
  easy_install pip
}

debian_prepare_packages() {
  # prepare postgresql utils and dev packages
  # required to build psycopg Python pgsql library
  sudo apt-get -y install postgresql postgresql-server-dev-all

  # prepare python tools
  sudo apt-get -y install -y python-dev python-pip make
}

prepare_packages() {
  if check_if_debian; then
    debian_prepare_pakages
  elif check_if_redhat; then
    redhat_prepare_packages
  else
    echo 'OS is not supported!'
    exit 1
  fi
}

prepare_venv() {
  # install venv tools
  sudo pip install virtualenv
  # activate venv
  virtualenv "${VENV}"  # you can use any name instead of 'fuel'
  . "${VENV}/bin/activate" # command selects the particular environment
  # install dependencies
  pip install ./shotgun  # this fuel project is listed in setup.py requirements
  pip install -r 'nailgun/test-requirements.txt'
}

view_file() {
  if [ "`uname`" = "Darwin" ]; then
    open "${1}"
  elif [ "`uname`" = "Linux" ]; then
    xdg-open "${1}"
  else
    echo 'OS is not supported!'
    exit 1
  fi 
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

build_pdf() {
  if !check_latex_present; then
    echo 'You need to install LaTeX if you want to build PDF!'
    exit 1
  fi
  make -C docs latexpdf
  if [ "${VIEW}" = '1' ]; then
    view_file "${PDF}"
  fi
}

build_epub() {
  make -C docs epub
  if [ "${VIEW}" = '1' ]; then
    view_file "${EPUB}"
  fi
}

show_help() {
cat <<EOF
Documentation build helper
-o - Open generated documentation after build
-f - Documentation format [html,signlehtml,pdf,epub]
EOF
}

# MAIN

while getopts ":ohf:" opt; do
  case $opt in
    o)
      VIEW='1'
      ;;
    h)
      show_help
      exit 0
      ;;
    f)
      echo "${OPTARG}"
      FORMAT="${OPTARG}"
      ;;
    \?)
      echo "Invalid option: -$OPTARG" >&2
      show_help
      exit 1
      ;;
  esac
done

if !check_java_present; then
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
epub)
  build_epub
  ;;
*)
  echo "Format ${FORMAT} is not supported!"
  exit 1
  ;;
esac
