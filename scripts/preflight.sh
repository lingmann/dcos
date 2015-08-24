#!/bin/bash

export OVERALL_RC=0

function version_gt()
{
    HIGHEST_VERSION="$(echo "$@" | tr " " "\n" | sort -V | tail -n 1)"
    test $HIGHEST_VERSION == "$1"
}

function print_status()
{
    if [[ $1 == 0 ]]; then
        echo 'PASS'
    else
        echo 'FAIL'
    fi
}

function check_command()
{
    COMMAND=$1
    echo -n "Checking $COMMAND is installed and in PATH: "
    $( command -v $COMMAND >/dev/null 2>&1 || exit 1 )
    RC=$?
    print_status $RC
    return $RC
}

function check_docker_version()
{
    VERSION_ATLEAST=$1
    DOCKER_VERSION=$(docker --version | cut -f3 -d' ' | cut -f1 -d',')

    echo -n "Checking Docker version requirement (>= $VERSION_ATLEAST): "
    version_gt $DOCKER_VERSION $VERSION_ATLEAST 
    RC=$?
    print_status $RC
    return $RC
}


function check_all()
{
    check_command docker
    check_docker_version 1.7

    check_command wget
    check_command bash
    
    check_command python3
}

check_all
