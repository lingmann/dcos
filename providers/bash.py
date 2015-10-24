#!/usr/bin/env python3
"""Generates a bash script for installing DCOS On-Prem."""

from pkgpanda.util import write_string
import util


"""
Templates for use in on-premise bash-type installations of DCOS
"""

file_template = """mkdir -p `dirname {filename}`
cat <<'EOF' > "{filename}"
{content}
EOF
chmod {mode} {filename}

"""

bash_template = """#!/bin/bash
#
# BASH script to install DCOS on a node
#
# Usage:
#
#   dcos_install.sh <role>...
#
#
# Metadata:
#   dcos image commit: {{dcos_image_commit}}
#   generation date: {{generation_date}}
#
# TODO(cmaloney): Copyright + License string here

set -o errexit -o nounset -o pipefail

declare -i OVERALL_RC=0
declare -i PREFLIGHT_ONLY=0
declare -i DISABLE_PREFLIGHT=0

declare ROLES=""
declare RED=""
declare BOLD=""
declare NORMAL=""

# Check if this is a terminal, and if colors are supported, set some basic
# colors for outputs
if [ -t 1 ]; then
    colors_supported=$(tput colors)
    if [[ $colors_supported -ge 8 ]]; then
        RED='\e[1;31m'
        BOLD='\e[1m'
        NORMAL='\e[0m'
    fi
fi

# Setup getopt argument parser
ARGS=$(getopt -o dph --long "disable-preflight,preflight-only,help" -n "$(basename "$0")" -- "$@")

if [[ $EUID -ne 0 ]]; then
    echo "This script must be run as root" 1>&2
    exit 1
fi

function setup_directories() {
    echo -e "Creating directories under /etc/mesosphere"
    mkdir -p /etc/mesosphere/roles
    mkdir -p /etc/mesosphere/setup-flags
}

function setup_dcos_roles() {
    # Set DCOS roles
    for role in "$ROLES"
    do
        echo "Creating role file for ${role}"
        touch "/etc/mesosphere/roles/$role"
    done
}

# Set DCOS machine configuration
function configure_dcos() {
echo -e 'Configuring DCOS'
{{setup_flags}}
}

# Install the DCOS services, start DCOS
function setup_and_start_services() {
echo -e 'Setting and starting DCOS'
{{setup_services}}
}

set +e

declare -i DISABLE_VERSION_CHECK=0

# check if sort -V works
function check_sort_capability() {
    $( echo '1' | sort -V >/dev/null 2>&1 || exit 1 )
    RC=$?
    if [[ "$RC" -eq "2" ]]; then
        echo -e "${RED}Disabling version checking as sort -V is not available${NORMAL}"
        DISABLE_VERSION_CHECK=1
    fi
}

function version_gt() {
    # sort -V does version-aware sort
    HIGHEST_VERSION="$(echo "$@" | tr " " "\n" | sort -V | tail -n 1)"
    test $HIGHEST_VERSION == "$1"
}

function print_status() {
    CODE_TO_TEST=$1
    EXTRA_TEXT=${2:-}
    if [[ $CODE_TO_TEST == 0 ]]; then
        echo -e "${BOLD}PASS $EXTRA_TEXT${NORMAL}"
    else
        echo -e "${RED}FAIL $EXTRA_TEXT${NORMAL}"
    fi
}

function check_command_exists() {
    COMMAND=$1
    DISPLAY_NAME=${2:-$COMMAND}

    echo -e -n "Checking if $DISPLAY_NAME is installed and in PATH: "
    $( command -v $COMMAND >/dev/null 2>&1 || exit 1 )
    RC=$?
    print_status $RC
    (( OVERALL_RC += $RC ))
    return $RC
}

function check_version() {
    COMMAND_NAME=$1
    VERSION_ATLEAST=$2
    COMMAND_VERSION=$3
    DISPLAY_NAME=${4:-$COMMAND}

    echo -e -n "Checking $DISPLAY_NAME version requirement (>= $VERSION_ATLEAST): "
    version_gt $COMMAND_VERSION $VERSION_ATLEAST
    RC=$?
    print_status $RC "${NORMAL}($COMMAND_VERSION)"
    (( OVERALL_RC += $RC ))
    return $RC
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
  echo -e -n "Checking if port $PORT (required by $NAME) is in use: "
  RC=0
  cat /proc/net/{udp*,tcp*} | cut -d: -f3 | cut -d' ' -f1 | grep -q $(printf "%04x" $PORT) && RC=1
  print_status $RC
  (( OVERALL_RC += $RC ))
}

function check_preexisting_dcos() {
    echo -e -n 'Checking if DCOS is already installed: '
    if [[ ( -d /etc/systemd/system/dcos.target ) || \
       ( -d /etc/systemd/system/dcos.target.wants ) || \
       ( -d /opt/mesosphere ) ]]; then
        # this will print: Checking if DCOS is already installed: FAIL (Currently installed)
        print_status 1 "${NORMAL}(Currently installed)"
        echo
        cat <<EOM
Found an existing DCOS installation. To reinstall DCOS on this this machine you must
first uninstall DCOS then run dcos_install.sh. To uninstall DCOS, follow the product
documentation provided with DCOS.
EOM
        echo
        exit 1
    else
        print_status 0 "${NORMAL}(Not installed)"
    fi
}

function check_all() {
    # Disable errexit because we want the preflight checks to run all the way
    # through and not bail in the middle, which will happen as it relies on
    # error exit codes
    set +e
    echo -e "${BOLD}Running preflight checks${NORMAL}"

    check_preexisting_dcos

    check_sort_capability

    docker_version=$(docker version 2>/dev/null | awk '
        BEGIN { version=0 }
        {
            if($1 == "Server:") {
                server=1
                client=0
            } else if($1 == "Client:") {
                server=0
                client=1
            } else if ($1 == "Server" && $2 == "version:") {
                version=$3
                exit
            }
            if(server && $1 == "Version:") {
                version=$2
                exit
            }
        }
        END { print version }
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

    echo -e -n "Checking if group 'nogroup' exists: "
    getent group nogroup > /dev/null
    RC=$?
    print_status $RC
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

    for role in "$ROLES"
    do
        if [ "$role" != "master" -a "$role" != "slave" -a "$role" != "slave_public" ]; then
            echo -e "${RED}FAIL Invalid role $role. Role must be one of {master,slave,slave_public}{NORMAL}"
            (( OVERALL_RC += 1 ))
        fi
    done


    return $OVERALL_RC
}

function dcos_install()
{
    # Enable errexit
    set -e

    setup_directories
    setup_dcos_roles
    configure_dcos
    setup_and_start_services

}

function usage()
{
    echo -e "${BOLD}Usage: $0 [--disable-preflight|--preflight-only] <roles>${NORMAL}"
}

function main()
{
    eval set -- "$ARGS"

    while true ; do
        case "$1" in
            -d|--disable-preflight) DISABLE_PREFLIGHT=1;  shift  ;;
            -p|--preflight-only) PREFLIGHT_ONLY=1 ; shift  ;;
            -h|--help) usage; exit 1 ;;
            --) shift ; break ;;
            *) usage ; exit 1 ;;
        esac
    done

    if [[ $DISABLE_PREFLIGHT -eq 1 && $PREFLIGHT_ONLY -eq 1 ]]; then
        echo -e 'Both --disable-preflight and --preflight-only can not be specified'
        usage
        exit 1
    fi

    shift $(($OPTIND - 1))
    ROLES=$@

    if [[ $PREFLIGHT_ONLY -eq 1 ]] ; then
        check_all
    else
        if [[ -z $ROLES ]] ; then
            echo -e 'Atleast one role name must be specified'
            usage
            exit 1
        fi
        echo -e "${BOLD}Starting DCOS Install Process${NORMAL}"
        if [[ $DISABLE_PREFLIGHT -eq 0 ]] ; then
            check_all
            RC=$?
            if [[ $RC -ne 0 ]]; then
                echo 'Preflight checks failed. Exiting installation. Please consult product documentation'
                exit $RC
            fi
        fi
        # Run actual install
        dcos_install
    fi

}

# Run it all
main

"""


def generate(gen_out, output_dir):
    print("Generating Bash configuration files for DCOS")
    make_bash(gen_out)
    util.do_bundle_onprem(['dcos_install.sh'], gen_out, output_dir)


def make_bash(gen_out):
    """
    Reformat the cloud-config into bash heredocs
    Assert the cloud-config is only write_files
    """
    setup_flags = ""
    cloud_config = gen_out.templates['cloud-config']
    assert len(cloud_config) == 1
    for file_dict in cloud_config['write_files']:
        # NOTE: setup-packages is explicitly disallowed. Should all be in extra
        # cluster packages.
        assert 'setup-packages' not in file_dict['path']
        setup_flags += file_template.format(
            filename=file_dict['path'],
            content=file_dict['content'],
            mode=oct(file_dict.get('permissions', 0o644))[2:],
            owner=file_dict.get('owner', 'root'),
            group=file_dict.get('group', 'root')
            )

    # Reformat the DCOS systemd units to be bash written and started.
    # Write out the units as files
    setup_services = ""
    for service in gen_out.templates['dcos-services']:
        setup_services += file_template.format(
            filename='/etc/systemd/system/{}'.format(service['name']),
            content=service['content'],
            mode='644',
            owner='root',
            group='root'
            )

    setup_services += "\n"

    # Start, enable services which request it.
    for service in gen_out.templates['dcos-services']:
        assert service['name'].endswith('.service')
        name = service['name'][:-8]
        if service.get('enable'):
            setup_services += "systemctl enable {}\n".format(name)
        if service.get('command') == 'start':
            setup_services += "systemctl start {}\n".format(name)

    # Populate in the bash script template
    bash_script = util.jinja_env.from_string(bash_template).render(
        dcos_image_commit=util.dcos_image_commit,
        generation_date=util.template_generation_date,
        setup_flags=setup_flags,
        setup_services=setup_services,
        )

    # Output the dcos install script
    write_string('dcos_install.sh', bash_script)

    return 'dcos_install.sh'
