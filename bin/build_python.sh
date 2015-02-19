#!/bin/bash
set -o errexit -o nounset -o pipefail -x

function usage {
cat <<USAGE
 USAGE: `basename "$0"`
  Builds Python inside a docker container.
  
 Required environment variables:
  PKG_VER
  PKG_REL
  PYTHON_VER
USAGE
}; function --help { usage ;}; function -h { usage ;};

function globals {
  export PKG_VER
  export PKG_REL
  export PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
}; globals

function main {
  check_prereqs
  build
  create_symlinks
  copy_shared_libs
  msg "Finished building Python"
}

function check_prereqs {
  : ${PKG_VER:?"ERROR: PKG_VER must be set"}
  : ${PKG_REL:?"ERROR: PKG_REL must be set"}
  : ${PYTHON_VER:?"ERROR: PYTHON_VER must be set"}
}

function python_download {
  pushd "${PROJECT_ROOT}/build"
  curl -o Python-${PYTHON_VER}.tgz https://www.python.org/ftp/python/${PYTHON_VER}/Python-${PYTHON_VER}.tgz && \
  tar xzvf Python-${PYTHON_VER}.tgz && \
  mv Python-${PYTHON_VER} python-build . && \
  rm -f Python-${PYTHON_VER}.tgz
  popd
}

function python_configure {
  pushd "${PROJECT_ROOT}/build/python-build"
  ./configure --prefix="/opt/mesosphere/dcos/${PKG_VER}-${PKG_REL}/python"
  popd
}

function build {
  mkdir -p "${PROJECT_ROOT}/build/python-toor"
  python_download
  python_configure
  pushd "${PROJECT_ROOT}/build/python-build"
  make
  make install DESTDIR="${PROJECT_ROOT}/build/python-toor"
  popd
}

function copy_shared_libs {
  local libdir="${PROJECT_ROOT}/build/python-toor/opt/mesosphere/dcos/${PKG_VER}-${PKG_REL}/python/lib"
  :
}

function create_symlinks {
  pushd "${PROJECT_ROOT}/build/python-toor/opt/mesosphere/dcos/${PKG_VER}-${PKG_REL}/python/bin"
  ln -s python3.4m python3.4
  ln -s python3 python
  ln -s easy_install-3.4 easy_install-3
  ln -s easy_install-3 easy_install
  ln -s pip3 pip
  popd
}

function msg { out "$*" >&2 ;}
function err { local x=$? ; msg "$*" ; return $(( x == 0 ? 1 : x )) ;}
function out { printf '%s\n' "$*" ;}

if [[ ${1:-} ]] && declare -F | cut -d' ' -f3 | fgrep -qx -- "${1:-}"
then "$@"
else main "$@"
fi
