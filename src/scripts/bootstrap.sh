#!/bin/bash
set -o errexit -o nounset -o pipefail

function globals {
  # Any variables starting with SUBST_ are injected by build system
  # Set REPO_ROOT to the direct path to avoid cloudfront caching issues while
  # in development.
  export REPO_ROOT="https://s3.amazonaws.com/downloads.mesosphere.io/dcos"
  export DCOS_PKG_VER="${SUBST_PKG_VER}"
  export DCOS_PKG_REL="${SUBST_PKG_REL}"
  export EXTRACT_TO="/opt/mesosphere/dcos/${DCOS_PKG_VER}-${DCOS_PKG_REL}"
}; globals

function usage {
cat <<USAGE
 USAGE: `basename $0`
  Bootstraps DCOS v${DCOS_PKG_VER}-${DCOS_PKG_REL}
USAGE
}; function --help { usage ;}; function -h { usage ;};

function main {
  local fn_base="dcos-${DCOS_PKG_VER}-${DCOS_PKG_REL}"
  local dl_base="${REPO_ROOT}/${DCOS_PKG_VER}-${DCOS_PKG_REL}/${fn_base}"
  check_perms
  download "${dl_base}.manifest" > "/tmp/${fn_base}.manifest"
  download "${dl_base}.sha256"   > "/tmp/${fn_base}.sha256"
  download "${dl_base}.tgz"      > "/tmp/${fn_base}.tgz"
  verify "/tmp/${fn_base}.sha256"
  install "/tmp/${fn_base}.tgz"
  set_latest
  configure_zookeeper
  msg "Bootstrap complete"
}

# Download $1 and send contents to STDOUT
function download {
  msg "Downloading $1"
  wget -qO- "$1"
}

# Verify the checksum contained in file $1
function verify {
  msg "Verifying checksums in $1"
  pushd $(dirname "$1") 1>/dev/null
  sha256sum -c --quiet "$1"
  popd 1>/dev/null
}

# Install the tarball file $1
function install {
  msg "Installing DCOS from $1"
  mkdir -p "$EXTRACT_TO"
  $(cd "$EXTRACT_TO" && tar xzf "$1")
}

function check_perms {
  if (( $EUID != 0 )); then err "Please run as root"; fi
}

# Update latest symlink to point to extracted DCOS
function set_latest {
  pushd /opt/mesosphere/dcos
  ln -s "${DCOS_PKG_VER}-${DCOS_PKG_REL}" latest_tmp
  # Atomic symlink update
  mv -Tf latest_tmp latest
  popd
}

# TODO: Move config logic to something that can be parameterized at boot time
function configure_zookeeper {
  cat <<'EOF' > "/opt/mesosphere/dcos/latest/zookeeper/conf/zoo.cfg"
tickTime=2000
dataDir=/var/lib/zookeeper
clientPort=2181
EOF
}

function msg { out "$*" >&2 ;}
function err { local x=$? ; msg "$*" ; return $(( $x == 0 ? 1 : $x )) ;}
function out { printf '%s\n' "$*" ;}

if [[ ${1:-} ]] && declare -F | cut -d' ' -f3 | fgrep -qx -- "${1:-}"
then "$@"
else main "$@"
fi
