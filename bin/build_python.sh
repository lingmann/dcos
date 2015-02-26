#!/bin/bash
set -o errexit -o nounset -o pipefail

function usage {
cat <<USAGE
 USAGE: `basename "$0"`
  Builds Python inside a docker container.
  
 Required environment variables:
  PKG_VER
  PKG_REL
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
  if [ ! -d "${PROJECT_ROOT}/ext/python" ]
  then
    err "ERROR: expecting python source at ${PROJECT_ROOT}/ext/python"
  fi
}

function python_configure {
  mkdir -p "${PROJECT_ROOT}/build/python-build"
  pushd "${PROJECT_ROOT}/build/python-build"
  # --enable-new-dtags sets both RPATH and RUNPATH, see: ld(1)
  "${PROJECT_ROOT}/ext/python/configure" \
    --enable-shared \
    --prefix="/opt/mesosphere/dcos/${PKG_VER}-${PKG_REL}" \
    LDFLAGS="-Wl,-rpath=/opt/mesosphere/dcos/${PKG_VER}-${PKG_REL}/lib,--enable-new-dtags"
  popd
}

function build {
  python_configure
  pushd "${PROJECT_ROOT}/build/python-build"
  make
  mkdir -p "${PROJECT_ROOT}/build/python-toor"
  make install DESTDIR="${PROJECT_ROOT}/build/python-toor"
  popd
}

function copy_shared_libs {
  local libdir="${PROJECT_ROOT}/build/python-toor/opt/mesosphere/dcos/${PKG_VER}-${PKG_REL}/lib"
  :
}

function create_symlinks {
  pushd "${PROJECT_ROOT}/build/python-toor/opt/mesosphere/dcos/${PKG_VER}-${PKG_REL}/bin"
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
