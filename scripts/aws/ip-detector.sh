#!/bin/sh

get_private_ip_from_metaserver()
{
    wget -q -O - http://169.254.169.254/latest/meta-data/local-ipv4
}

echo ${COREOS_PRIVATE_IPV4:-$(get_private_ip_from_metaserver)}
