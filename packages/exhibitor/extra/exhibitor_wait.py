#!/opt/mesosphere/bin/python

import sys
import json
import codecs
import urllib.request

EXHIBITOR_STATUS_URL = 'http://127.0.0.1:8181/exhibitor/v1/cluster/status'

cluster_size = int(open('/opt/mesosphere/etc/master_count').read().strip())

try:
    response = urllib.request.urlopen(EXHIBITOR_STATUS_URL)
except urllib.error.URLError:
    print('Could not get exhibitor status: {}'.format(
        EXHIBITOR_STATUS_URL), file=sys.stderr)
    sys.exit(1)
reader = codecs.getreader("utf-8")
data = json.load(reader(response))

serving = 0
leaders = 0
for node in data:
    if node['isLeader']:
        leaders += 1
    if node['description'] == 'serving':
        serving += 1

if serving != cluster_size or leaders != 1:
    print('Expected {} servers and 1 leader, got {} servers and {} leaders'.format(
        cluster_size, serving, leaders), file=sys.stderr)
    sys.exit(1)

sys.exit(0)
