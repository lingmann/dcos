#!/bin/bash
set -o nounset -o pipefail -o errexit

if [ "$#" -ne 2 ]; then
    echo "Usage: create.sh <cluster-name> <num-nodes>"
    exit 1
fi

name=$1
nodes=$2

< azuredeploy-parameters.json tr '\n' ' '  | sed "s/_NAME_/$name/g;s/_NODES_/$nodes/" > /tmp/customparams.json
azure group create "$name" "East Asia" -f azuredeploy.json -d "$name" -e /tmp/customparams.json

echo "Created group $name"
