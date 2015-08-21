#!/usr/bin/env bash
set -eou pipefail
PATH=$PATH:/usr/sbin:/sbin

INT_IF=eth1

INT_NET=$(ip addr show "$INT_IF" | awk '/inet / { print $2; exit }')
INT_IP=$(echo "$INT_NET" | cut -d/ -f1)

echo "$INT_IP"
