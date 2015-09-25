#!/bin/bash
set -o nounset -o pipefail -o errexit

azure group delete -q "$1"
