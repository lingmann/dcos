#!/bin/bash
set -o nounset -o pipefail -o errexit

azure group create "$1" "West US" -f azuredeploy.json -d "$1" -e azuredeploy-parameters.json
