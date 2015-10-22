#!/bin/sh
set -o errexit -o nounset

source /etc/environment
echo $COREOS_PRIVATE_IPV4
