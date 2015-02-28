#!/bin/bash
set -o errexit -o nounset -o pipefail

function usage {
cat <<USAGE
 USAGE: `basename "$0"` command [args]

  Convert stdout and stderr from the given command to annotated stdout and
  stderr streams. For example:

   $ `basename "$0"` echo "stdout"
   stdout: stdout
 
   $ `basename "$0"` ls /invalid_path
   stderr: ls: /invalid_path: No such file or directory

  Note: Ordering is *not* preserved.

USAGE
}; function --help { usage ;}; function -h { usage ;};

function main {
  # Use process substitution to directly hook up stdout and stderr to separate
  # sed instances. See: http://goo.gl/iwZkp
  "$@" > >(sed 's/^/stdout: /') 2> >(sed 's/^/stderr: /' >&2)
}

if [[ ${1:-} ]] && declare -F | cut -d' ' -f3 | fgrep -qx -- "${1:-}"
then "$@"
else main "$@"
fi
