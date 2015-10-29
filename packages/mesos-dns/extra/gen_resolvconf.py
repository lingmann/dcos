#!/opt/mesosphere/bin/python

import os
import socket
import sys
import json
import codecs
import random
import urllib.request

import dns.query


EXHIBITOR_STATUS_URL = 'http://{}:8181/exhibitor/v1/cluster/status'

if len(sys.argv) != 2:
    print('Usage: gen_resolvconf.py RESOLV_CONF_PATH', file=sys.stderr)
    print('Received: {}'.format(sys.argv), file=sys.stderr)
    sys.exit(-1)
resolvconf_path = sys.argv[1]
dns_test_query = 'master.mesos'
dns_timeout = 5


def get_masters_exhibitor():
    status_url = EXHIBITOR_STATUS_URL.format(os.environ['EXHIBITOR_ADDRESS'])
    try:
        servers = []
        response = urllib.request.urlopen(status_url)
        reader = codecs.getreader("utf-8")
        data = json.load(reader(response))
        for node in data:
            servers.append(socket.gethostbyname(node['hostname']))

        return servers
    except:
        print('Error getting list of masters from exhibitor {}: {}'.format(
                (status_url), sys.exc_info()[1]), file=sys.stderr)
        return []


def get_masters_file():
    return json.load(open('/opt/mesosphere/etc/master_list', 'r'))


def check_server(addr):
    try:
        query = dns.message.make_query(dns_test_query, dns.rdatatype.ANY)
        result = dns.query.udp(query, addr, dns_timeout)
        if len(result.answer) == 0:
            print('Skipping DNS server {}: no records for {}'.format(addr, dns_test_query), file=sys.stderr)
        else:
            return True
    except socket.gaierror as ex:
        print(ex, file=sys.stderr)
    except dns.exception.Timeout:
        print('Skipping DNS server {}: no response'.format(addr), file=sys.stderr)
    except:
        print("Unexpected error querying DNS for server \"{}\" exception: {}".format(addr, sys.exc_info()[1]))

    return False

mesos_dns_servers = []
master_source = os.environ['MASTER_SOURCE']
if master_source == 'exhibitor':
    mesos_dns_servers += get_masters_exhibitor()
elif master_source == 'master_list':
    mesos_dns_servers += get_masters_file()

# Test potential servers, throwing out unreachable ones.
up_master_nameservers = []
for addr in mesos_dns_servers:
    if check_server(addr):
        up_master_nameservers.append(addr)

# Fill up nameservers via the various sources until we hit MAXNS.
max_ns = 3
needed_server_count = 3
final_nameservers = []

# If try_localhost, always give that as first option
if os.environ.get('TRY_LOCALHOST', "false") == "true":
    if check_server("127.0.0.1"):
        final_nameservers.append("127.0.0.1")
        needed_server_count -= 1

# Pick up to two servers at random, giving us a max three total servers per
# resolv.h MAXNS, with a good fallback dns server always present as the last in
# the set.
if len(up_master_nameservers) >= needed_server_count - 1:
    final_nameservers += random.sample(up_master_nameservers, needed_server_count - 1)
else:
    random.shuffle(up_master_nameservers)
    final_nameservers += up_master_nameservers

needed_server_count = max_ns - len(final_nameservers)

# Append fallback resolvers to fill out MAXNS
fallback_servers = os.environ['RESOLVERS'].split(',')
if len(fallback_servers) >= needed_server_count:
    final_nameservers += random.sample(fallback_servers, needed_server_count)
else:
    final_nameservers += fallback_servers

# Generate the resolv.conf config
print('Updating {}'.format(resolvconf_path))
with open(resolvconf_path, 'w') as f:
    print("options timeout:1", file=f)
    print("options attempts:3", file=f)
    print("options timeout:1", file=sys.stderr)
    print("options attempts:3", file=sys.stderr)
    for ns in final_nameservers:
        line = "nameserver {}".format(ns)
        print(line, file=sys.stderr)
        print(line, file=f)

sys.exit(0)
