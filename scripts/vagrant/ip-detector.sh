#!/usr/bin/env bash

get_defaultish_ip()
{
    ipv4=$(ip route get 8.8.8.8 | awk '{print $7; exit}')
    echo $ipv4
}

echo ${COREOS_PRIVATE_IPV4:-$(get_defaultish_ip)}
