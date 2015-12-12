#!/bin/bash
# Execute preflight checks
# Ripped off off from install_dcos.sh
set -o errexit -o nounset -o pipefail

declare -i OVERALL_RC=0
declare -i PREFLIGHT_ONLY=0
declare -i DISABLE_PREFLIGHT=0

declare ROLES=""
declare -i DISABLE_VERSION_CHECK=0


function print_status() {
  CODE_TO_TEST=$1
  MESSAGE=${2:-}
  if [[ $CODE_TO_TEST == 0 ]]; then
    echo -e "PASS::$MESSAGE"
  else
    echo -e "FAIL::$MESSAGE"
  fi
}

function version_gt() {
    # sort -V does version-aware sort
    HIGHEST_VERSION="$(echo "$@" | tr " " "\n" | sort -V | tail -n 1)"
    test $HIGHEST_VERSION == "$1"
}

function check_command_exists() {
  COMMAND=$1
  DISPLAY_NAME=${2:-$COMMAND}

  $( command -v $COMMAND >/dev/null 2>&1 || exit 1 )
  RC=$?
  

  print_status $RC "$1 exists?"
  (( OVERALL_RC += $RC ))
  return $RC
}

function check_version() {
  COMMAND_NAME=$1
  VERSION_ATLEAST=$2
  COMMAND_VERSION=$3
  DISPLAY_NAME=${4:-$COMMAND}

  version_gt $COMMAND_VERSION $VERSION_ATLEAST
  RC=$?
  
  print_status $RC "$COMMAND_NAME version $COMMAND_VERSION acceptable?"
  (( OVERALL_RC += $RC ))
  return $RC
}

function check_selinux() {
  ENABLED=$(sestatus | grep 'SELinux status' | cut -d: -f 2 | sed  -E "s/[[:space:]]+//g")
  
  if [[ $ENABLED == 'enabled' ]]; then 
    RC=1
  else
    RC=0
  fi

  print_status $RC "SELinux disabled?"
  return $RC
}

function check_disk_space() {
  # Check each available /dev mount 
  for disk in $(mount | grep "^/dev" | awk '{print $1}'); do
    # Get the size in human readable format
    size=$(df $disk | awk '{print $2}' | tail -1)
    if [ $size -lt  8000000 ]; then
      RC=1
      print_status $RC "Disk space greater than 8GB? $disk: $size"
    else
      RC=0
      print_status $RC "Disk space greater than 8GB? $disk: $size"
    fi  
  done

}

function check() {
  # Wrapper to invoke both check_commmand and version check in one go
  if [[ $# -eq 4 ]]; then
   DISPLAY_NAME=$4
  elif [[ $# -eq 2 ]]; then
   DISPLAY_NAME=$2
  else
   DISPLAY_NAME=$1
  fi
  check_command_exists $1 $DISPLAY_NAME
  # check_version takes {3,4} arguments
  if [[ "$#" -ge 3 && $DISABLE_VERSION_CHECK -eq 0 ]]; then
    check_version $*
  fi
}

function check_service() {
  PORT=$1
  NAME=$2
  RC=0
  cat /proc/net/{udp*,tcp*} | cut -d: -f3 | cut -d' ' -f1 | grep -q $(printf "%04x" $PORT) && RC=1
  print_status $RC ":$PORT open? (required by $NAME)"
  (( OVERALL_RC += $RC ))
}

function check_preexisting_dcos() {
  if [[ ( -d /etc/systemd/system/dcos.target ) || \
   ( -d /etc/systemd/system/dcos.target.wants ) || \
   ( -d /opt/mesosphere ) ]]; then
    # this will print: Checking if DCOS is already installed: FAIL (Currently installed)
    print_status 1 "DCOS currently installed?"
    echo
    cat <<EOM
Found an existing DCOS installation. To reinstall DCOS on this this machine you must
first uninstall DCOS then run dcos_install.sh. To uninstall DCOS, follow the product
documentation provided with DCOS.
EOM
    echo
    exit 1
  else
    print_status 0 "DCOS currently installed?"
  fi
}

function check_all() {
  # Disable errexit because we want the preflight checks to run all the way
  # through and not bail in the middle, which will happen as it relies on
  # error exit codes
  set +e

  check_preexisting_dcos
  check_selinux
  check_disk_space
  #check_sort_capability

  local docker_version=$(docker version 2>/dev/null | awk '
    BEGIN {
        version = 0
        client_version = 0
        server_version = 0
    }
    {
        if($1 == "Server:") {
      server = 1
      client = 0
        } else if($1 == "Client:") {
      server = 0
      client = 1
        } else if ($1 == "Server" && $2 == "version:") {
      server_version = $3
        } else if ($1 == "Client" && $2 == "version:") {
      client_version = $3
        }
        if(server && $1 == "Version:") {
      server_version = $2
        } else if(client && $1 == "Version:") {
      client_version = $2
        }
    }
    END {
        if(client_version == server_version) {
      version = client_version
        } else {
      split(client_version, cv, ".")
      split(server_version, sv, ".")

      y = length(cv) > length(sv) ? length(cv) : length(sv)

      for(i = 1; i <= y; i++) {
          if(cv[i] < sv[i]) {
        version = client_version
        break
          } else if(sv[i] < cv[i]) {
        version = server_version
        break
          }
      }
        }
        print version
    }
  ')
  # CoreOS stable as of Aug 2015 has 1.6.2
  check docker 1.6 "$docker_version"

  check curl
  check bash
  check ping
  check tar
  check xz
  check unzip

  # $ systemctl --version ->
  # systemd nnn
  # compiler option string
  # Pick up just the first line of output and get the version from it
  check systemctl 200 $(systemctl --version | head -1 | cut -f2 -d' ') systemd

  getent group nogroup > /dev/null
  RC=$?
  print_status $RC "group 'nogroup' exists?"
  (( OVERALL_RC += $RC ))

  for service in \
    "80 mesos-ui" \
    "53 mesos-dns" \
    "15055 dcos-history" \
    "5050 mesos-master" \
    "2181 zookeeper" \
    "8080 marathon" \
    "3888 zookeeper" \
    "8181 exhibitor" \
    "8123 mesos-dns"
  do
    check_service $service
  done

  return $OVERALL_RC
}

check_all
