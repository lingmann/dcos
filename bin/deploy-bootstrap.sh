#!/bin/bash
set -o errexit -o nounset -o pipefail

function usage {
cat <<USAGE
 USAGE: `basename $0`
  Update the bootstrap.sh script on S3 (downloads.mesosphere.io/dcos/)
USAGE
}; function --help { usage ;}; function -h { usage ;};

function globals {
  export PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
}; globals

function main {
  aws s3 cp "${PROJECT_ROOT}/scripts/bootstrap.sh" \
    s3://downloads.mesosphere.io/dcos/
}

function msg { out "$*" >&2 ;}
function err { local x=$? ; msg "$*" ; return $(( $x == 0 ? 1 : $x )) ;}
function out { printf '%s\n' "$*" ;}

if [[ ${1:-} ]] && declare -F | cut -d' ' -f3 | fgrep -qx -- "${1:-}"
then "$@"
else main "$@"
fi
