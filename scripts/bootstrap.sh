#!/bin/bash
set -o errexit -o nounset -o pipefail

function usage {
cat <<USAGE
 USAGE: `basename $0`
  Bootstraps the DCOS. Latest version can be retrieved from:
  https://downloads.mesosphere.io/dcos/bootstrap.sh
USAGE
}; function --help { usage ;}; function -h { usage ;};

function globals {
  export REPO_ROOT="https://downloads.mesosphere.io"
  export DCOS_TARBALL="dcos-0.0.1-0.1.20150130221546.4f9f3e0.tgz"
  export JAVA_TARBALL="jre-7u75-linux-x64.tar.gz"
  export ZOOKEEPER_TARBALL="zookeeper-3.4.6.tar.gz"
  export MARATHON_TARBALL="marathon-0.8.0-RC1.tgz"
}; globals

function main {
  update_environment
  install_dcos
  install_java
  install_zookeeper
  configure_zookeeper
  install_marathon
  msg "Bootstrap complete"
}

function install_dcos {
  cd /
  wget -nv "${REPO_ROOT}/dcos/${DCOS_TARBALL}" -O "$DCOS_TARBALL"
  tar xzf "$DCOS_TARBALL"
  # Atomic symlink update
  ln -s /opt/mesosphere/dcos/$(latest_dir /opt/mesosphere/dcos "*") \
    /opt/mesosphere/dcos/latest_tmp && \
    mv -Tf /opt/mesosphere/dcos/latest_tmp /opt/mesosphere/dcos/latest
}

function install_java {
  local workdir="/opt/mesosphere/dcos/latest"
  cd "$workdir"
  wget -nv "${REPO_ROOT}/java/${JAVA_TARBALL}" -O "$JAVA_TARBALL"
  tar xzf "${JAVA_TARBALL}"
  rm -f "${workdir}/java"
  ln -s "${workdir}/$(latest_dir $workdir "jre*")" "${workdir}/java"
}

function install_marathon {
  local workdir="/opt/mesosphere/dcos/latest"
  cd "$workdir"
  wget -nv "${REPO_ROOT}/marathon/v0.8.0-RC1/${MARATHON_TARBALL}" \
    -O "$MARATHON_TARBALL"
  tar xzf "${MARATHON_TARBALL}"
  rm -f "${workdir}/marathon"
  ln -s "${workdir}/$(latest_dir $workdir "marathon*")" "${workdir}/marathon"
  rm -f "${workdir}/marathon/marathon.jar"
  ln -s "${workdir}"/marathon/target/*/marathon*.jar \
    "${workdir}/marathon/marathon.jar"
}

function install_zookeeper {
  local workdir="/opt/mesosphere/dcos/latest"
  cd "$workdir"
  wget -nv "${REPO_ROOT}/zookeeper/${ZOOKEEPER_TARBALL}" -O "$ZOOKEEPER_TARBALL"
  tar xzf "${ZOOKEEPER_TARBALL}"
  rm -f "${workdir}/zookeeper"
  ln -s "${workdir}/$(latest_dir $workdir "zookeeper*")" "${workdir}/zookeeper"
}

# TODO: Move config logic to something that can be parameterized at boot time
function configure_zookeeper {
  cat <<'EOF' > "/opt/mesosphere/dcos/latest/zookeeper/conf/zoo.cfg"
tickTime=2000
dataDir=/var/lib/zookeeper
clientPort=2181
EOF
}

# Update /etc/environment with EC2 instance metadata. Used to help Mesos and
# Marathon set a --hostname that will work internally and externally.
function update_environment {
  # Have curl fail on server errors (like 404's)
  public_hostname=$(curl -fsS http://169.254.169.254/latest/meta-data/public-hostname)
  echo EC2_PUBLIC_HOSTNAME="$public_hostname" >> /etc/environment
}

# Returns the latest directory found in $1 matching pattern $2
# example: $(latest_dir /opt/mesosphere/dcos "*") => "0.0.1-0.1.20150129223657"
function latest_dir {
  # $2 is left unquoted so that shell globs can be expanded
  local dir=$(cd "$1" && find $2 -maxdepth 0 -type d -exec ls -dt "{}" \;|tail -1)
  out "$dir"
}

function msg { out "$*" >&2 ;}
function err { local x=$? ; msg "$*" ; return $(( $x == 0 ? 1 : $x )) ;}
function out { printf '%s\n' "$*" ;}

if [[ ${1:-} ]] && declare -F | cut -d' ' -f3 | fgrep -qx -- "${1:-}"
then "$@"
else main "$@"
fi
