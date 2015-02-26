#!/bin/bash
set -o errexit -o nounset -o pipefail

function usage {
cat <<USAGE
 USAGE: `basename "$0"`
  Builds Mesos inside a docker container.
  
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
  copy_shared_libs
  patch_rpath
  msg "Finished building Mesos"
}

function check_prereqs {
  : ${PKG_VER:?"ERROR: PKG_VER must be set"}
  : ${PKG_REL:?"ERROR: PKG_REL must be set"}
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
    --prefix="/opt/mesosphere/dcos/${PKG_VER}-${PKG_REL}" \
    --enable-optimize --disable-python LDFLAGS="-Wl,-rpath=XORIGIN"
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
  local libdir="${PROJECT_ROOT}/build/mesos-toor/opt/mesosphere/dcos/${PKG_VER}-${PKG_REL}/lib"
  cp /usr/lib/x86_64-linux-gnu/libsasl2.so.2 "$libdir"
  cp /usr/lib/x86_64-linux-gnu/libsvn_delta-1.so.1 "$libdir"
  cp /usr/lib/x86_64-linux-gnu/libsvn_subr-1.so.1 "$libdir"
  cp /usr/lib/x86_64-linux-gnu/libapr-1.so.0 "$libdir"
  cp /usr/lib/x86_64-linux-gnu/libaprutil-1.so.0 "$libdir"
  cp "${PROJECT_ROOT}"/build/mesos-build/src/java/target/mesos-*.jar "$libdir"
}

# Return relative path from directory $2 (defaults to `pwd`) to directory $1.
# $1: /foo/
# $2: /foo/libexec/mesos/
# =>: ../..
function relative_path {
  python -c "import os.path; print os.path.relpath('$1','${2:-$PWD}')"
}

function patch_rpath {
  local rpath_regex='.*XORIGIN.*'
  local dcoslibdir="/opt/mesosphere/dcos/${PKG_VER}-${PKG_REL}/lib"
  local libdir="${PROJECT_ROOT}/build/mesos-toor${dcoslibdir}"
  while IFS= read -d $'\0' -r file
  do
    if [[ $(patchelf --print-rpath "$file" 2>/dev/null) =~ $rpath_regex ]]
    then
      local parent_dir=$(dirname "$file")
      local new_rpath="\$ORIGIN/$(relative_path "$libdir" "$parent_dir")"
      echo "Patching rpath on $file to $new_rpath"
      patchelf --set-rpath "$new_rpath" "$file"
    fi
  done < <(find "${PROJECT_ROOT}/build/mesos-toor" -type f -executable -print0)
}

function msg { out "$*" >&2 ;}
function err { local x=$? ; msg "$*" ; return $(( x == 0 ? 1 : x )) ;}
function out { printf '%s\n' "$*" ;}

if [[ ${1:-} ]] && declare -F | cut -d' ' -f3 | fgrep -qx -- "${1:-}"
then "$@"
else main "$@"
fi
