#!/bin/bash
set -o errexit -o nounset -o pipefail -x

function usage {
cat <<USAGE
 USAGE: `basename $0`
  Builds Mesos inside a docker container.
  
 Required environment variables:
  PKG_VER
  PKG_REL
USAGE
}; function --help { usage ;}; function -h { usage ;};

: ${PKG_VER:?"ERROR: PKG_VER must be set"}
: ${PKG_REL:?"ERROR: PKG_REL must be set"}

function globals {
  export PKG_VER
  export PKG_REL
  export PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
}; globals

function main {
  check_prereqs
  build
  copy_shared_libs
  msg "Finished building Mesos"
}

function check_prereqs {
  if [ ! -d "${PROJECT_ROOT}/ext/mesos" ]
  then
    err "ERROR: expecting directory at ${PROJECT_ROOT}/ext/mesos"
  fi
}

function mesos_bootstrap {
  pushd "${PROJECT_ROOT}/ext/mesos"
  ./bootstrap
  popd
}

function mesos_configure {
  pushd "${PROJECT_ROOT}/build/mesos-build"
  "${PROJECT_ROOT}/ext/mesos/configure" \
    --prefix="/opt/mesosphere/dcos/${PKG_VER}-${PKG_REL}/mesos" \
    --enable-optimize --disable-python
  popd
}

function build {
  mkdir -p "${PROJECT_ROOT}/build/mesos-build"
  mkdir -p "${PROJECT_ROOT}/build/mesos-toor"
  mesos_bootstrap
  mesos_configure
  pushd "${PROJECT_ROOT}/build/mesos-build"
  make
  make install DESTDIR="${PROJECT_ROOT}/build/mesos-toor"
  popd
}

function copy_shared_libs {
  local libdir="${PROJECT_ROOT}/build/mesos-toor/opt/mesosphere/dcos/${PKG_VER}-${PKG_REL}/mesos/lib"
  cp /usr/lib/x86_64-linux-gnu/libsasl2.so.2 "$libdir"
  cp /usr/lib/x86_64-linux-gnu/libsvn_delta-1.so.1 "$libdir"
  cp /usr/lib/x86_64-linux-gnu/libsvn_subr-1.so.1 "$libdir"
  cp /usr/lib/x86_64-linux-gnu/libapr-1.so.0 "$libdir"
  cp /usr/lib/x86_64-linux-gnu/libaprutil-1.so.0 "$libdir"
  cp build/mesos-build/src/java/target/mesos-*.jar "$libdir"
}

function msg { out "$*" >&2 ;}
function err { local x=$? ; msg "$*" ; return $(( $x == 0 ? 1 : $x )) ;}
function out { printf '%s\n' "$*" ;}

if [[ ${1:-} ]] && declare -F | cut -d' ' -f3 | fgrep -qx -- "${1:-}"
then "$@"
else main "$@"
fi
