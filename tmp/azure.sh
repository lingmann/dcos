#!/bin/bash
set -o errexit -o nounset -o pipefail

# TODO: Update template AZURE_PREFIX value...

function main {
  echo "stub"
}

function globals {
  num_masters=3
  image_id=2b171e93f07c4903bcad35bda10acf22__CoreOS-Beta-633.1.0
  user=core
  master_config=azure-master-slave.yaml
  vm_size=Medium
  ssh_cert=/Users/jlingmann/.ssh/id_rsa.default-mesosphere.pem
  location="West US"
}; globals

# Create Azure DCOS stack
# $1: stack UUID e.g. jeremy-msphere
function create {
  azure service create --location="$location" "$1"
  azure network vnet create --address-space=10.0.0.0 --cidr=8 \
    --subnet-name=mesos-cluster --subnet-start-ip=10.0.0.0 --subnet-cidr=11 \
    --location="$location" "$1"
  #azure service internal-load-balancer add --serviceName="$1" \
  #  --internalLBName=exhibitor --subnet-name=mesos-cluster \
  #  --static-virtualnetwork-ipaddress=10.0.0.4
  for ((n=0;n<$num_masters;n++))
  do
    master=$1-master${n}
    echo "Creating $master"
    azure vm create --custom-data="$master_config" --vm-size="$vm_size" \
      --ssh=220$n --ssh-cert="$ssh_cert" --no-ssh-password --vm-name="$master" \
      --availability-set=masters --connect="$1" --virtual-network-name="$1" \
      "$image_id" "$user"
    azure vm endpoint create-multiple "$master" 8181:8181:tcp:false:exhibitor:tcp:8181,2181:2181:tcp:false:zookeeper:tcp:2181,5050:5050:tcp:false:mesos-master:tcp:5050,8080:8080:tcp:false:marathon:tcp:8080,80:80:tcp:false:http:tcp:80
  done
  azure vm list | egrep "(Name|----|$1)"
}

# Destroy Azure DCOS stack. It's also possible to use the Azure web console to
# destroy the entire cloud service (likely the fastest way to destroy).
# $1: stack UUID e.g. jeremy-msphere
function destroy {
  for ((n=0;n<$num_masters;n++))
  do
    master=$1-master${n}
    echo "Destroying $master"
    azure vm delete -q "$master"
  done
  azure network vnet delete -q "$1"
  azure service delete -q "$1"
}

# Generate random n character alphanumeric string, n specified as $1
function uuid {
  out $(cat /dev/urandom | env LC_CTYPE=C tr -dc 'a-zA-Z0-9' | fold -w "$1" | head -n 1)
}

function msg { out "$*" >&2 ;}
function err { local x=$? ; msg "$*" ; return $(( x == 0 ? 1 : x )) ;}
function out { printf '%s\n' "$*" ;}

if [[ ${1:-} ]] && declare -F | cut -d' ' -f3 | fgrep -qx -- "${1:-}"
then "$@"
else main "$@"
fi
