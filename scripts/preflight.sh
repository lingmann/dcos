#!/bin/bash

set -o noglob -o nounset -o pipefail

declare -i OVERALL_RC=0

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


# check if sort -V works
declare -i DISABLE_VERSION_CHECK=0

function check_sort_capability()
{
    $( echo '1' | sort -V >/dev/null 2>&1 || exit 1 )
    RC=$?
    if [[ "$RC" -eq "2" ]]; then
        echo -e "${RED}Disabling version checking as sort -V is not available${NORMAL}"
        DISABLE_VERSION_CHECK=1
    fi
}


function version_gt()
{
    # sort -V does version-aware sort
    HIGHEST_VERSION="$(echo "$@" | tr " " "\n" | sort -V | tail -n 1)"
    test $HIGHEST_VERSION == "$1"
}

function print_status()
{
    CODE_TO_TEST=$1
    EXTRA_TEXT=${2:-}
    if [[ $CODE_TO_TEST == 0 ]]; then
        echo -e "${BOLD}PASS $EXTRA_TEXT${NORMAL}"
    else
        echo -e "${RED}FAIL $EXTRA_TEXT${NORMAL}"
    fi
}

function check_command()
{
    COMMAND=$1
    echo -e -n "Checking if $COMMAND is installed and in PATH: "
    $( command -v $COMMAND >/dev/null 2>&1 || exit 1 )
    RC=$?
    print_status $RC
    (( OVERALL_RC += $RC ))
    return $RC
}

function check_version()
{
    COMMAND_NAME=$1
    VERSION_ATLEAST=$2
    COMMAND_VERSION=$3

    echo -e -n "Checking $COMMAND_NAME version requirement (>= $VERSION_ATLEAST): "
    version_gt $COMMAND_VERSION $VERSION_ATLEAST
    RC=$?
    print_status $RC "${NORMAL}($COMMAND_VERSION)"
    (( OVERALL_RC += $RC ))
    return $RC
}

function check()
{
    # Wrapper to invoke both check_commmand and version check in one go
    check_command $*
    # check_version takes 3 arguments
    if [[ "$#" -eq 3 && $DISABLE_VERSION_CHECK -eq 0 ]]; then
        check_version $*
    fi
}

function check_all()
{
    check_sort_capability
    check docker 1.7 $(docker --version | cut -f3 -d' ' | cut -f1 -d',')

    check wget
    check bash
    check ping
    check tar 1.27 $(tar --version | head -1 | cut -f4 -d' ')
    check xz 5.0 $(xz --version | head -1 | cut -f4 -d' ')

    check systemd 215 $(systemd --version | head -1 | cut -f2 -d' ')

    return $OVERALL_RC
}
