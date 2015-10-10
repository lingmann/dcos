#!/bin/bash
set -o errexit -o nounset -o pipefail

function usage {
  cat <<USAGE
This script builds and publishes the mesosphere/dcos-genconf Docker image. At
build time, a "with-bootstrap" version of the image is also built containing the
bootstrap tarball and embedded into an installer script.

The Docker images will include the SHA of the components, as follows:

mesosphere/dcos-genconf:\${DCOS_IMAGE_SHA}-\${PKGPANDA_SHA}-\${BOOTSTRAP_ID}
mesosphere/dcos-genconf:with-bootstrap-\${DCOS_IMAGE_SHA}-\${PKGPANDA_SHA}-\${BOOTSTRAP_ID}

A tag in the format: \${DCOS_IMAGE_SHA}-\${PKGPANDA_SHA}-\${BOOTSTRAP_ID} is
written to a file name docker-tag in the current working directory. SHA's may
be shortened to an unambiguous length.

 The following environment variables must be set:
   export PKGPANDA_SRC=pkgpanda               # Set to pkgpanda git checkout
   export DCOS_IMAGE_SRC=dcos-image         # Set to dcos-image git checkout
   export CHANNEL_NAME=testing/continuous
   export BOOTSTRAP_ID=0026f44d8574d508104f1e7e7a163e078e69990b

 Building an image:
   ./$(basename "$0")

 Publishing an image to Docker hub:
   ./$(basename "$0") push

 Using image to generate DCOS config tarball:
   BUILD_DIR=/tmp/genconf
   # Place ip-detect.sh script in \$BUILD_DIR and mount in container at /genconf
   docker run -it -v "\$BUILD_DIR":/genconf mesosphere/dcos-genconf
   # Configuration tarball will be written to \$BUILD_DIR

USAGE
}

function globals {
  export MY_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/" && pwd )"
  export PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/../../" && pwd )"
  export BOOTSTRAP_ROOT="https://downloads.mesosphere.com/dcos"
  export LC_ALL=en_US.UTF-8                  # A locale that works consistently
}; globals

# Returns the build_dir
function get_build_dir {
  tmpdir=`mktemp -d 2>/dev/null || mktemp -d -t 'genconf'`
  mkdir -p "${tmpdir}"/pkgpanda "${tmpdir}"/dcos-image
  # clone the repository dropping git history other than last commit so that it
  # is still a valid git checkout but we lose any local modifications, and don't
  # capture any temporary files in the filesystem (package builds, etc).
  git clone --depth=1 "file://${PKGPANDA_SRC}" "${tmpdir}"/pkgpanda
  git clone --depth=1 "file://${DCOS_IMAGE_SRC}" "${tmpdir}"/dcos-image
  cat <<CONFIG_JSON > "${tmpdir}"/dcos-image/config.json
{
  "bootstrap_id":"$BOOTSTRAP_ID",
  "ip_detect_filename":"/genconf/ip-detect.sh",
  "channel_name":"${CHANNEL_NAME}"
}
CONFIG_JSON
  export DOCKER_TAG="$DOCKER_TAG"
  export BOOTSTRAP_FILENAME="${BOOTSTRAP_ID}.bootstrap.tar.xz"
  export BOOTSTRAP_TAR="${BOOTSTRAP_ROOT}/${CHANNEL_NAME}/bootstrap/$BOOTSTRAP_FILENAME"
  export GENCONF_TAR="$GENCONF_TAR"
  envsubst < "${MY_ROOT}"/Dockerfile.template > "${tmpdir}"/Dockerfile
  envsubst < "${MY_ROOT}"/Dockerfile-bootstrap.template > "${tmpdir}"/Dockerfile-bootstrap
  envsubst '$DOCKER_TAG:$GENCONF_TAR' < "${MY_ROOT}"/dcos_generate_config.sh.in > dcos_generate_config.sh
  out "$tmpdir"
}

function check_prereqs {
  if [[ -d "${PKGPANDA_SRC:=}" ]]
  then
    # Update to full path for Docker build
    PKGPANDA_SRC="$( cd "${PKGPANDA_SRC}" && pwd )"
  else
    msg "ERROR: PKGPANDA_SRC var is not set to a valid directory"
    exit 1
  fi

  if [[ -d "${DCOS_IMAGE_SRC:=}" ]]
  then
    # Update to full path for Docker build
    DCOS_IMAGE_SRC="$( cd "${DCOS_IMAGE_SRC}" && pwd )"
  else
    msg "ERROR: DCOS_IMAGE_SRC env var is not set to a valid directory"
    exit 1
  fi

  DCOS_IMAGE_SHA=$(git -C "${DCOS_IMAGE_SRC}" rev-parse HEAD || true)
  : ${DCOS_IMAGE_SHA:?"ERROR: Unable to determine Git SHA of DCOS_IMAGE"}

  PKGPANDA_SHA=$(git -C "${PKGPANDA_SRC}" rev-parse HEAD || true)
  : ${PKGPANDA_SHA:?"ERROR: Unable to determine Git SHA of PKGPANDA"}

  : ${CHANNEL_NAME:?"ERROR: CHANNEL_NAME env var must be set"}
  : ${BOOTSTRAP_ID:?"ERROR: BOOTSTRAP_ID env var must be set"}

  DOCKER_TAG="${DCOS_IMAGE_SHA:0:12}-${PKGPANDA_SHA:0:12}-${BOOTSTRAP_ID:0:12}"
  GENCONF_TAR="dcos-genconf.${DOCKER_TAG}.tar"
}

function main {
  check_prereqs
  build_dir=$(get_build_dir)
  build "$build_dir"
  cleanup "$build_dir"
}

# Builds the Docker image located in $1
function build {
  check_prereqs
  echo "Building: $1"
  pushd "$1"
  docker build -t mesosphere/dcos-genconf:"${DOCKER_TAG}" .
  docker build -t mesosphere/dcos-genconf:"with-bootstrap-${DOCKER_TAG}" - < Dockerfile-bootstrap
  popd
  echo "$DOCKER_TAG" > docker-tag

  echo "Building dcos_genergate_config.sh"
  docker save mesosphere/dcos-genconf:"with-bootstrap-${DOCKER_TAG}" > "$GENCONF_TAR"
  tar cvf - "$GENCONF_TAR" >> dcos_generate_config.sh
  chmod +x dcos_generate_config.sh
}

# Push the built image to Docker hub
function push {
  check_prereqs
  CHANNEL_NAME_SANITIZED=$(echo $CHANNEL_NAME | tr '/' '_')
  dest_id=mesosphere/dcos-genconf:"${DOCKER_TAG}"
  dest_channel=mesosphere/dcos-genconf:"${CHANNEL_NAME_SANITIZED}"
  echo "Pushing: ${dest_id} and ${dest_channel}"
  docker push "$dest_id"
  docker tag -f "$dest_id" "$dest_channel"
  docker push "$dest_channel"
}

# Removes the directory specified by $1
function cleanup {
  if [[ -d "$1" ]]
  then
    echo "Cleaning up $1"
    rm -rf "$1"
  else
    msg "No such directory: $1"
    exit 1
  fi
  rm -rf "$GENCONF_TAR"
}

function msg { out "$*" >&2 ;}
function err { local x=$? ; msg "$*" ; return $(( x == 0 ? 1 : x )) ;}
function out { printf '%s\n' "$*" ;}

if [[ ${1:-} ]] && declare -F | cut -d' ' -f3 | fgrep -qx -- "${1:-}"
then "$@"
elif [[ ${1:-} == '-h' || ${1:-} == 'help' || ${1:-} == '--help' ]]
then
  usage
else main "$@"
fi
