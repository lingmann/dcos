

scripts = {
    'aws': """
#!/bin/sh
# Example ip-detect script using an external authority
# Uses the AWS Metadata Service to get the node's internal
# ipv4 address
curl -fsSL http://169.254.169.254/latest/meta-data/local-ipv4
""",
    'azure': """
#!/bin/sh
set -o nounset -o errexit

# Get COREOS COREOS_PRIVATE_IPV4
if [ -e /etc/environment ]
then
  set -o allexport
  . /etc/environment
  set +o allexport
fi

# Get the IP address of the interface specified by $1
get_ip_from_interface()
{
  /sbin/ifconfig "$1" | awk '/(inet addr)/ { print $2 }' | cut -d":" -f2 | head -1
}

echo ${COREOS_PRIVATE_IPV4:-$(get_ip_from_interface eth0)}
""",
    'vagrant': """
#!/usr/bin/env bash
set -o nounset -o errexit

# Get COREOS COREOS_PRIVATE_IPV4
if [ -e /etc/environment ]
then
  set -o allexport
  source /etc/environment
  set +o allexport
fi


get_defaultish_ip()
{
    ipv4=$(ip route get 8.8.8.8 | awk '{print $7; exit}')
    echo $ipv4
}

echo ${COREOS_PRIVATE_IPV4:-$(get_defaultish_ip)}
""",
    'custom': """
# Example custom script, assumes a ethernet device of eth0.
#!/usr/bin/env bash
set -o nounset -o errexit
export PATH=/usr/sbin:/usr/bin:$PATH
echo $(ip addr show eth0 | grep -Eo '[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}' | head -1)
"""
}
