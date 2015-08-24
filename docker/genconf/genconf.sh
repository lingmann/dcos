#!/bin/bash
set -o errexit -o nounset -o pipefail

function usage {
cat <<USAGE
Generates DCOS configuration for BOOTSTRAP_ID: $(bootstrap_id)
 USAGE:
   # Interactively generate a new DCOS configuration
   # Place ip-detect.sh in \$BUILD_DIR and volume mount to /genconf
   # Configuration tarball will be written to \$BUILD_DIR
   docker run -it -v "\$BUILD_DIR":/genconf mesosphere/dcos-genconf:$(bootstrap_id) interactive
USAGE
}

function globals {
  export MY_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
}; globals

function interactive {
  if [[ -f /genconf/ip-detect.sh ]]
  then
    /dcos-image/bash.py --output-dir /genconf --config config.json
  else
    msg "ERROR: Missing /genconf/ip-detect.sh"
    usage
    exit 1
  fi
}

function bootstrap_id {
  tar=$(echo /dcos-image/packages/*.bootstrap.tar.xz)
  if test -e $tar
  then
    base=$(basename "$tar")
    id="${base%%.*}"
    out "$id"
  else
    msg "ERROR: Expecting a single bootstrap tarball in /dcos-image/packages"
    exit 1
  fi
}

function msg { out "$*" >&2 ;}
function err { local x=$? ; msg "$*" ; return $(( x == 0 ? 1 : x )) ;}
function out { printf '%s\n' "$*" ;}

if [[ ${1:-} ]] && declare -F | cut -d' ' -f3 | fgrep -qx -- "${1:-}"
then "$@"
else usage
fi
